"""
@Auth ：挂科边缘
@File ：AICSMain.py
@IDE ：PyCharm
@Motto :学习新思想，争做新青年
"""
import os
import sys
sys.path.append('desktop-app')
from utils.AIChatMessage import AIChatMessageWindow, RoleType
from api_client import ApiError, DesktopApiClient
sys.path.append('ui/AI')
from PySide6.QtGui import QGuiApplication
from PySide6.QtWidgets import QApplication
from ui.AI.AICS import Ui_AIMainWindow
from PySide6.QtCore import QDateTime, QSize, Qt, QEvent, QThread, Signal
from PySide6.QtWidgets import QMainWindow, QListWidgetItem
from utils.UserInfo import UserInfo
from utils.message import DialogOver
py_minor = sys.version_info.minor
if py_minor == 9:
    from utils.py39.main_utils import (
        get_windows_scaling_factor, get_screen_resolution)
elif py_minor == 10:
    from utils.py310.main_utils import (
        get_windows_scaling_factor, get_screen_resolution)
elif py_minor == 11:
    from utils.py311.main_utils import (
        get_windows_scaling_factor, get_screen_resolution)
elif py_minor == 7:
    from utils.py37.main_utils import (
        get_windows_scaling_factor, get_screen_resolution)
elif py_minor == 8:
    from utils.py38.main_utils import (
        get_windows_scaling_factor, get_screen_resolution)
else:
    raise RuntimeError(
        f"请使用python版本为3.9"
    )


# Threads detached from a closed window are parked here until they finish, so
# they are neither garbage-collected while running nor able to touch destroyed
# widgets (their signals are disconnected before parking).
_ORPHAN_THREADS = []


def _park_orphan_thread(thread):
    _ORPHAN_THREADS.append(thread)

    def _cleanup():
        if thread in _ORPHAN_THREADS:
            _ORPHAN_THREADS.remove(thread)
        thread.deleteLater()

    thread.finished.connect(_cleanup)


class ChatApiThread(QThread):
    start_signal = Signal(dict)
    chunk_signal = Signal(str)
    response_signal = Signal(dict)
    error_signal = Signal(str)
    complete_signal = Signal()

    def __init__(self, access_token, question, conversation_id=None):
        super().__init__()
        self.access_token = access_token
        self.question = question
        self.conversation_id = conversation_id
        self.api_client = DesktopApiClient()

    def run(self):
        try:
            for event in self.api_client.stream_chat(
                self.access_token,
                self.question,
                conversation_id=self.conversation_id,
            ):
                if self.isInterruptionRequested():
                    return
                event_type = event.get("type")
                if event_type == "start":
                    self.start_signal.emit(event)
                elif event_type == "chunk":
                    self.chunk_signal.emit(event.get("delta", ""))
                elif event_type == "done":
                    self.response_signal.emit(event)
                elif event_type == "error":
                    self.error_signal.emit(event.get("message", "聊天请求失败"))
        except ApiError as exc:
            self.error_signal.emit(exc.message)
        except Exception as exc:
            self.error_signal.emit(f"聊天请求失败: {exc}")
        finally:
            self.complete_signal.emit()


class AgentApiThread(QThread):
    """Phase 6A-3 — streams POST /api/agent/chat/stream via DesktopApiClient."""

    start_signal = Signal(dict)
    chunk_signal = Signal(str)
    response_signal = Signal(dict)
    error_signal = Signal(str)
    complete_signal = Signal()

    def __init__(self, access_token, message, conversation_id=None, mode="auto", detection_id=None):
        super().__init__()
        self.access_token = access_token
        self.message = message
        self.conversation_id = conversation_id
        self.mode = mode or "auto"
        self.detection_id = detection_id
        self.api_client = DesktopApiClient()

    def run(self):
        try:
            for event in self.api_client.stream_agent_chat(
                self.access_token,
                self.message,
                conversation_id=self.conversation_id,
                mode=self.mode,
                detection_id=self.detection_id,
            ):
                if self.isInterruptionRequested():
                    return
                event_type = event.get("type")
                if event_type == "start":
                    self.start_signal.emit(event)
                elif event_type == "chunk":
                    self.chunk_signal.emit(event.get("delta", ""))
                elif event_type == "done":
                    self.response_signal.emit(event)
                elif event_type == "error":
                    self.error_signal.emit(event.get("message", "Agent 请求失败"))
        except ApiError as exc:
            self.error_signal.emit(exc.message)
        except Exception as exc:
            self.error_signal.emit(f"Agent 请求失败: {exc}")
        finally:
            self.complete_signal.emit()


class AIWindow(QMainWindow, Ui_AIMainWindow):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setupUi(self)
        self.pushButton_Submit.clicked.connect(self.on_pushButton_Submit_clicked)
        self.textEdit_input.installEventFilter(self)
        self.chat_thread = None
        self.current_conversation_id = None

        # Phase 6A-3 minimal agent mode toggle.
        # If the UI file does not expose a dedicated toggle widget, we create
        # a simple in-memory flag that can be toggled programmatically.
        # Set _agent_mode = True to route messages through /api/agent/chat/stream.
        self._agent_mode: bool = False
        self._agent_detection_id: int | None = None
        self._agent_mode_key: str = "auto"

    def eventFilter(self, obj, event):
        if obj == self.textEdit_input and event.type() == QEvent.KeyPress:
            if event.key() == Qt.Key_Enter or event.key() == Qt.Key_Return:
                if event.modifiers() & Qt.ShiftModifier:
                    # 按下 Shift+Enter 插入换行
                    cursor = self.textEdit_input.textCursor()
                    cursor.insertText("\n")
                    return True  # 事件被处理，避免传递到其他控件
                else:
                    # 按下 Enter 键发送消息
                    self.on_pushButton_Submit_clicked()
                    return True
        return super().eventFilter(obj, event)

    def on_pushButton_Submit_clicked(self):
        if self.chat_thread is not None and self.chat_thread.isRunning():
            DialogOver(parent=self, text="上一条消息仍在处理中", title="提示", flags="warning")
            return

        message = self.textEdit_input.toPlainText().strip()
        if message == "":
            return

        try:
            access_token = self._get_access_token()
        except ApiError as exc:
            DialogOver(parent=self, text=exc.message, title="错误", flags="warning")
            return

        self.textEdit_input.clear()
        time = str(int(QDateTime.currentDateTime().toSecsSinceEpoch()))  # 获取时间戳
        self.updateMessageTimeDisplay(time)
        user_window = AIChatMessageWindow(self.listWidget_out.parentWidget())
        user_item = QListWidgetItem(self.listWidget_out)
        self.updateMessageDisplay(user_window, user_item, message, time, RoleType.user)

        self.current_message_window = AIChatMessageWindow(self.listWidget_out.parentWidget())
        self.current_item = QListWidgetItem(self.listWidget_out)
        self.pushButton_Submit.setEnabled(False)

        if self._agent_mode:
            self.chat_thread = AgentApiThread(
                access_token,
                message,
                conversation_id=self.current_conversation_id,
                mode=self._agent_mode_key,
                detection_id=self._agent_detection_id,
            )
        else:
            self.chat_thread = ChatApiThread(access_token, message, conversation_id=self.current_conversation_id)

        self.chat_thread.start_signal.connect(self.on_api_start)
        self.chat_thread.chunk_signal.connect(self.on_api_chunk)
        self.chat_thread.response_signal.connect(self.on_api_response)
        self.chat_thread.error_signal.connect(self.on_api_error)
        self.chat_thread.complete_signal.connect(self.on_api_complete)
        self.chat_thread.start()

        self.listWidget_out.setCurrentRow(self.listWidget_out.count() - 1)

    def on_api_start(self, payload):
        conversation_id = payload.get("conversation_id")
        if conversation_id:
            self.current_conversation_id = conversation_id

    def on_api_chunk(self, delta):
        if not delta:
            return
        time = str(int(QDateTime.currentDateTime().toSecsSinceEpoch()))
        if hasattr(self, 'current_item') and self.current_item:
            current_message_window = self.current_message_window
            current_text = current_message_window.message_text or ""
            current_text += delta
            self.updateMessageDisplay(current_message_window, self.current_item, current_text, time, RoleType.system)
            self.listWidget_out.setCurrentRow(self.listWidget_out.count() - 1)

    def on_api_response(self, response):
        conversation_id = response.get("conversation_id")
        if conversation_id:
            self.current_conversation_id = conversation_id

    def on_api_error(self, error_message):
        time = str(int(QDateTime.currentDateTime().toSecsSinceEpoch()))
        if hasattr(self, 'current_item') and self.current_item:
            self.updateMessageDisplay(
                self.current_message_window,
                self.current_item,
                error_message,
                time,
                RoleType.system,
            )
            self.listWidget_out.setCurrentRow(self.listWidget_out.count() - 1)

    def on_api_complete(self):
        self.pushButton_Submit.setEnabled(True)
        if self.chat_thread is not None:
            self.chat_thread.deleteLater()
            self.chat_thread = None

    def updateMessageDisplay(self, message_window, current_item, text, time, userType):
        message_window.setFixedWidth(self.width())  # 设置消息窗口的宽度为主窗口的宽度
        size = message_window.font_rect(text)  # 获取文本的矩形区域
        current_item.setSizeHint(QSize(self.width(), size.height()))  # 设置列表项的高度为文本高度
        message_window.setText(text, time, size, userType)
        self.listWidget_out.setItemWidget(current_item, message_window)  # 将消息添加到消息列表中

    # 处理消息的时间显示
    def updateMessageTimeDisplay(self, curMsgTime):
        if self.listWidget_out.count() > 0:
            lastItem = self.listWidget_out.item(self.listWidget_out.count() - 1)
            message_window = self.listWidget_out.itemWidget(lastItem)
            lastTime = int(message_window.message_time)  # 获取最后一条消息的时间戳
            curTime = int(curMsgTime)  # 获取当前时间戳
            show_time = (curTime - lastTime) > 60  # 如果两条消息相差超过60秒，显示时间
        else:
            show_time = True

        if show_time:
            messageTime = AIChatMessageWindow(self.listWidget_out.parentWidget())
            itemTime = QListWidgetItem(self.listWidget_out)
            size = QSize(self.width(), 40)
            messageTime.resize(size)
            itemTime.setSizeHint(size)
            messageTime.setText(curMsgTime, curMsgTime, size, RoleType.current_time)
            self.listWidget_out.setItemWidget(itemTime, messageTime)

    def resizeEvent(self, event):
        for i in range(self.listWidget_out.count()):
            current_message_window = self.listWidget_out.itemWidget(self.listWidget_out.item(i))
            current_item = self.listWidget_out.item(i)
            self.updateMessageDisplay(current_message_window, current_item, current_message_window.message_text,
                                      current_message_window.message_time, current_message_window.message_userType)
        super().resizeEvent(event)

    def closeEvent(self, event):
        # 關窗時把仍在串流的 thread「斷開」：先斷 signal 再要求中斷，
        # 避免 worker thread 對已銷毀的 widget 發 signal 造成 crash。
        thread = self.chat_thread
        if thread is not None and thread.isRunning():
            for signal in (
                thread.start_signal,
                thread.chunk_signal,
                thread.response_signal,
                thread.error_signal,
                thread.complete_signal,
            ):
                try:
                    signal.disconnect()
                except (RuntimeError, TypeError):
                    pass
            thread.requestInterruption()
            _park_orphan_thread(thread)
            self.chat_thread = None
        super().closeEvent(event)

    def enable_agent_mode(self, mode: str = "auto", detection_id: int | None = None) -> None:
        """Switch to LangGraph agent backend (Phase 6A-3 minimal integration).

        Call this from MainUI or any other launcher to route future messages
        through ``POST /api/agent/chat/stream`` instead of ``/api/chat/stream``.
        Subsequent messages will use the provided ``mode`` and optional
        ``detection_id`` until :meth:`disable_agent_mode` is called.

        Args:
            mode: One of ``auto`` / ``general_chat`` / ``explain_detection`` /
                ``history_analysis`` / ``report`` / ``admin_help``.
            detection_id: Optional detection task id for explain / report modes.
        """
        self._agent_mode = True
        self._agent_mode_key = mode or "auto"
        self._agent_detection_id = detection_id
        self.current_conversation_id = None  # start a fresh agent conversation

    def disable_agent_mode(self) -> None:
        """Revert to the standard provider-based chat backend."""
        self._agent_mode = False
        self._agent_mode_key = "auto"
        self._agent_detection_id = None
        self.current_conversation_id = None

    @staticmethod
    def _get_access_token():
        user_info = UserInfo()
        user_token, _ = user_info.load_user_token()
        if user_token:
            return user_token

        admin_token, _ = user_info.load_admin_token()
        if admin_token:
            return admin_token

        raise ApiError("请先登录后再使用 AI 对话")


if __name__ == '__main__':
    resolution = get_screen_resolution()
    if resolution is not None:
        width, height = resolution
    scaling_factor = get_windows_scaling_factor()
    if resolution and (width > 1920 or height > 1080):
        QGuiApplication.setHighDpiScaleFactorRoundingPolicy(Qt.HighDpiScaleFactorRoundingPolicy.Ceil)
        dpi = int(scaling_factor * 96)
    elif (width == 1920 and height == 1080) and scaling_factor < 1.50:
        QGuiApplication.setHighDpiScaleFactorRoundingPolicy(Qt.HighDpiScaleFactorRoundingPolicy.PassThrough)
        dpi = 144
    else:
        QGuiApplication.setHighDpiScaleFactorRoundingPolicy(Qt.HighDpiScaleFactorRoundingPolicy.PassThrough)
        dpi = int(scaling_factor * 96)

    if scaling_factor is not None:
        os.environ["QT_FONT_DPI"] = str(dpi)
    app = QApplication(sys.argv)
    view = AIWindow()
    view.show()
    sys.exit(app.exec())
