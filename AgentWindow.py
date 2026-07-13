"""
AgentWindow.py — Phase 6A-3 Desktop Agent Console

Standalone PySide6 QDialog that connects to POST /api/agent/chat/stream.
Reuses the AIChatMessageWindow bubble pattern from AICSMain.py.

Opening from MainUI:
    from AgentWindow import AgentWindow
    win = AgentWindow(parent=self, mode="explain_detection", detection_id=123)
    win.exec()

Or stand-alone (for development):
    python AgentWindow.py
"""
from __future__ import annotations

import os
import sys

sys.path.append("desktop-app")

from PySide6.QtCore import QDateTime, QEvent, QSize, Qt, QThread, Signal
from PySide6.QtWidgets import (
    QApplication,
    QComboBox,
    QDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QTextEdit,
    QVBoxLayout,
)

from api_client import ApiError, DesktopApiClient
from utils.AIChatMessage import AIChatMessageWindow, RoleType
from utils.UserInfo import UserInfo

# ---------------------------------------------------------------------------
# Mode definitions (mirrors backend ALLOWED_AGENT_MODES)
# ---------------------------------------------------------------------------

AGENT_MODES: list[tuple[str, str]] = [
    ("auto",              "自動偵測 (Auto)"),
    ("general_chat",      "一般對話 (General Chat)"),
    ("explain_detection", "解釋偵測結果 (Explain Detection)"),
    ("history_analysis",  "偵測歷史分析 (History Analysis)"),
    ("report",            "產出報告 (Report)"),
    ("admin_help",        "管理員輔助 (Admin Help)"),
]

# Threads detached from a closed window are parked here until they finish, so
# they are neither garbage-collected while running nor able to touch destroyed
# widgets (their signals are disconnected before parking).
_ORPHAN_THREADS: list[QThread] = []


def _park_orphan_thread(thread: QThread) -> None:
    _ORPHAN_THREADS.append(thread)

    def _cleanup() -> None:
        if thread in _ORPHAN_THREADS:
            _ORPHAN_THREADS.remove(thread)
        thread.deleteLater()

    thread.finished.connect(_cleanup)


# ---------------------------------------------------------------------------
# Background thread
# ---------------------------------------------------------------------------

class AgentStreamThread(QThread):
    """Calls POST /api/agent/chat/stream and emits SSE events as Qt signals."""

    start_signal = Signal(dict)
    chunk_signal = Signal(str)
    response_signal = Signal(dict)
    error_signal = Signal(str)
    complete_signal = Signal()

    def __init__(
        self,
        access_token: str,
        message: str,
        conversation_id: str | None = None,
        mode: str = "auto",
        detection_id: int | None = None,
    ) -> None:
        super().__init__()
        self.access_token = access_token
        self.message = message
        self.conversation_id = conversation_id
        self.mode = mode or "auto"
        self.detection_id = detection_id
        self._api = DesktopApiClient()

    def run(self) -> None:
        try:
            for event in self._api.stream_agent_chat(
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
                    self.error_signal.emit(event.get("message", "Agent 請求失敗"))
        except ApiError as exc:
            self.error_signal.emit(exc.message)
        except Exception as exc:
            self.error_signal.emit(f"Agent 請求失敗：{exc}")
        finally:
            self.complete_signal.emit()


# ---------------------------------------------------------------------------
# Main dialog
# ---------------------------------------------------------------------------

class AgentWindow(QDialog):
    """Standalone Desktop Agent Console Dialog.

    Args:
        parent: Parent widget (typically the MainUI Client window).
        mode:   Pre-selected agent mode key (default ``"auto"``).
        detection_id: Pre-filled detection task id for explain / report modes.
    """

    def __init__(
        self,
        parent=None,
        mode: str = "auto",
        detection_id: int | None = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("AI Agent Console")
        self.setMinimumSize(720, 560)
        self.resize(820, 640)

        self._thread: AgentStreamThread | None = None
        self._conversation_id: str | None = None
        self._current_bubble: AIChatMessageWindow | None = None
        self._current_item: QListWidgetItem | None = None

        self._build_ui()
        self._set_initial_mode(mode)
        if detection_id is not None:
            self._detection_id_edit.setText(str(detection_id))

    # ------------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------------

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setSpacing(10)
        root.setContentsMargins(14, 14, 14, 14)

        # ── Top controls ──────────────────────────────────────────────
        top_row = QHBoxLayout()

        mode_label = QLabel("Mode：")
        mode_label.setFixedWidth(52)
        self._mode_combo = QComboBox()
        for key, label in AGENT_MODES:
            self._mode_combo.addItem(label, key)
        self._mode_combo.setMinimumWidth(210)

        did_label = QLabel("Detection ID：")
        self._detection_id_edit = QLineEdit()
        self._detection_id_edit.setPlaceholderText("選填，例：123")
        self._detection_id_edit.setMaximumWidth(110)

        new_btn = QPushButton("New Conversation")
        new_btn.clicked.connect(self._on_new_conversation)

        top_row.addWidget(mode_label)
        top_row.addWidget(self._mode_combo)
        top_row.addSpacing(16)
        top_row.addWidget(did_label)
        top_row.addWidget(self._detection_id_edit)
        top_row.addStretch()
        top_row.addWidget(new_btn)
        root.addLayout(top_row)

        # ── Conversation list ─────────────────────────────────────────
        self._list_widget = QListWidget()
        self._list_widget.setSpacing(4)
        root.addWidget(self._list_widget, stretch=1)

        # ── Text input ────────────────────────────────────────────────
        self._text_input = QTextEdit()
        self._text_input.setPlaceholderText(
            "輸入訊息，按 Enter 送出 / Shift+Enter 換行"
        )
        self._text_input.setFixedHeight(84)
        self._text_input.installEventFilter(self)
        root.addWidget(self._text_input)

        # ── Submit row ────────────────────────────────────────────────
        submit_row = QHBoxLayout()
        self._status_label = QLabel("")
        self._status_label.setStyleSheet("color: #61758a; font-size: 12px;")
        submit_row.addWidget(self._status_label)
        submit_row.addStretch()
        self._submit_btn = QPushButton("送出")
        self._submit_btn.setMinimumWidth(110)
        self._submit_btn.clicked.connect(self._on_submit)
        submit_row.addWidget(self._submit_btn)
        root.addLayout(submit_row)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _set_initial_mode(self, mode: str) -> None:
        for i, (key, _) in enumerate(AGENT_MODES):
            if key == mode:
                self._mode_combo.setCurrentIndex(i)
                return

    def _selected_mode(self) -> str:
        return self._mode_combo.currentData() or "auto"

    def _selected_detection_id(self) -> int | None:
        text = self._detection_id_edit.text().strip()
        return int(text) if text.isdigit() else None

    @staticmethod
    def _get_access_token() -> str:
        info = UserInfo()
        user_token, _ = info.load_user_token()
        if user_token:
            return user_token
        admin_token, _ = info.load_admin_token()
        if admin_token:
            return admin_token
        raise ApiError("請先登入後再使用 AI Agent")

    # ------------------------------------------------------------------
    # Event filter — Enter to send
    # ------------------------------------------------------------------

    def eventFilter(self, obj, event):
        if obj is self._text_input and event.type() == QEvent.KeyPress:
            if event.key() in (Qt.Key_Return, Qt.Key_Enter):
                if event.modifiers() & Qt.ShiftModifier:
                    self._text_input.textCursor().insertText("\n")
                    return True
                self._on_submit()
                return True
        return super().eventFilter(obj, event)

    # ------------------------------------------------------------------
    # Slots
    # ------------------------------------------------------------------

    def _on_new_conversation(self) -> None:
        if self._thread and self._thread.isRunning():
            return
        self._conversation_id = None
        self._list_widget.clear()
        self._status_label.setText("")

    def _on_submit(self) -> None:
        if self._thread and self._thread.isRunning():
            return

        message = self._text_input.toPlainText().strip()
        if not message:
            return

        try:
            token = self._get_access_token()
        except ApiError as exc:
            self._status_label.setText(f"⚠ {exc.message}")
            return

        mode = self._selected_mode()
        detection_id = self._selected_detection_id()

        self._text_input.clear()
        self._submit_btn.setEnabled(False)
        self._status_label.setText("Agent 處理中…")

        now = str(int(QDateTime.currentDateTime().toSecsSinceEpoch()))
        self._append_time_bubble(now)

        # User bubble
        user_bubble = AIChatMessageWindow(self._list_widget.parentWidget() or self)
        user_item = QListWidgetItem(self._list_widget)
        self._render_bubble(user_bubble, user_item, message, now, RoleType.user)

        # Assistant placeholder
        self._current_bubble = AIChatMessageWindow(self._list_widget.parentWidget() or self)
        self._current_item = QListWidgetItem(self._list_widget)

        self._thread = AgentStreamThread(
            token,
            message,
            conversation_id=self._conversation_id,
            mode=mode,
            detection_id=detection_id,
        )
        self._thread.start_signal.connect(self._on_start)
        self._thread.chunk_signal.connect(self._on_chunk)
        self._thread.response_signal.connect(self._on_response)
        self._thread.error_signal.connect(self._on_error)
        self._thread.complete_signal.connect(self._on_complete)
        self._thread.start()

        self._list_widget.scrollToBottom()

    def _on_start(self, payload: dict) -> None:
        if payload.get("conversation_id"):
            self._conversation_id = payload["conversation_id"]

    def _on_chunk(self, delta: str) -> None:
        if not delta or not self._current_bubble or not self._current_item:
            return
        now = str(int(QDateTime.currentDateTime().toSecsSinceEpoch()))
        current_text = (self._current_bubble.message_text or "") + delta
        self._render_bubble(self._current_bubble, self._current_item, current_text, now, RoleType.system)
        self._list_widget.scrollToBottom()

    def _on_response(self, payload: dict) -> None:
        if payload.get("conversation_id"):
            self._conversation_id = payload["conversation_id"]

    def _on_error(self, error_message: str) -> None:
        now = str(int(QDateTime.currentDateTime().toSecsSinceEpoch()))
        if self._current_bubble and self._current_item:
            self._render_bubble(
                self._current_bubble,
                self._current_item,
                f"[錯誤] {error_message}",
                now,
                RoleType.system,
            )
            self._list_widget.scrollToBottom()
        self._status_label.setText(f"⚠ {error_message}")

    def _on_complete(self) -> None:
        self._submit_btn.setEnabled(True)
        self._status_label.setText("")
        if self._thread:
            self._thread.deleteLater()
            self._thread = None

    # ------------------------------------------------------------------
    # Bubble rendering helpers
    # ------------------------------------------------------------------

    def _render_bubble(
        self,
        bubble: AIChatMessageWindow,
        item: QListWidgetItem,
        text: str,
        time_str: str,
        role: int,
    ) -> None:
        usable_width = max(self.width() - 28, 200)
        bubble.setFixedWidth(usable_width)
        size = bubble.font_rect(text)
        item.setSizeHint(QSize(usable_width, size.height()))
        bubble.setText(text, time_str, size, role)
        self._list_widget.setItemWidget(item, bubble)

    def _append_time_bubble(self, cur_time: str) -> None:
        count = self._list_widget.count()
        if count > 0:
            last_item = self._list_widget.item(count - 1)
            last_w = self._list_widget.itemWidget(last_item)
            if last_w and hasattr(last_w, "message_time"):
                try:
                    last_ts = int(last_w.message_time)
                    if int(cur_time) - last_ts <= 60:
                        return
                except (ValueError, TypeError):
                    pass

        time_bubble = AIChatMessageWindow(self._list_widget.parentWidget() or self)
        time_item = QListWidgetItem(self._list_widget)
        size = QSize(self.width() - 28, 40)
        time_bubble.resize(size)
        time_item.setSizeHint(size)
        time_bubble.setText(cur_time, cur_time, size, RoleType.current_time)
        self._list_widget.setItemWidget(time_item, time_bubble)

    # ------------------------------------------------------------------
    # Close — detach the streaming thread so it can't touch dead widgets
    # ------------------------------------------------------------------

    def _detach_stream_thread(self) -> None:
        thread = self._thread
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
        self._thread = None
        self._current_bubble = None
        self._current_item = None

    def closeEvent(self, event) -> None:
        self._detach_stream_thread()
        super().closeEvent(event)

    def reject(self) -> None:  # Esc key closes a QDialog via reject()
        self._detach_stream_thread()
        super().reject()

    # ------------------------------------------------------------------
    # Resize — re-render all bubbles to fit new width
    # ------------------------------------------------------------------

    def resizeEvent(self, event) -> None:
        for i in range(self._list_widget.count()):
            item = self._list_widget.item(i)
            w = self._list_widget.itemWidget(item)
            if w and hasattr(w, "message_text") and w.message_text:
                self._render_bubble(w, item, w.message_text, w.message_time, w.message_userType)
        super().resizeEvent(event)


# ---------------------------------------------------------------------------
# Stand-alone entry point (for development / testing)
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    py_minor = sys.version_info.minor
    try:
        if py_minor == 11:
            from utils.py311.main_utils import get_screen_resolution, get_windows_scaling_factor
        elif py_minor == 10:
            from utils.py310.main_utils import get_screen_resolution, get_windows_scaling_factor
        elif py_minor == 9:
            from utils.py39.main_utils import get_screen_resolution, get_windows_scaling_factor
        else:
            raise ImportError
    except ImportError:
        get_screen_resolution = lambda: (1920, 1080)  # noqa: E731
        get_windows_scaling_factor = lambda: 1.0  # noqa: E731

    from PySide6.QtGui import QGuiApplication

    resolution = get_screen_resolution()
    if resolution:
        width, height = resolution
    scaling_factor = get_windows_scaling_factor() or 1.0

    if resolution and (width > 1920 or height > 1080):
        QGuiApplication.setHighDpiScaleFactorRoundingPolicy(
            Qt.HighDpiScaleFactorRoundingPolicy.Ceil
        )
        dpi = int(scaling_factor * 96)
    else:
        QGuiApplication.setHighDpiScaleFactorRoundingPolicy(
            Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
        )
        dpi = 144

    if scaling_factor:
        os.environ["QT_FONT_DPI"] = str(dpi)

    app = QApplication(sys.argv)
    win = AgentWindow(mode="auto")
    win.show()
    sys.exit(app.exec())
