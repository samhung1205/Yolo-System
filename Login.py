import datetime
import os
import sys

sys.path.append('ui/UserLogin')
sys.path.append('desktop-app')
import configparser
from PySide6.QtGui import QIcon, Qt, QPalette, QBrush, QPixmap, QGuiApplication, QPainter
from PySide6.QtWidgets import QMainWindow, QApplication
from Register import RegisterClient
from ui.UserLogin.login import Ui_LoginMainWindow
import re
from api_client import ApiError, DesktopApiClient
from ui_state import SI
from utils.message import DialogOver
from utils.UserInfo import UserInfo
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
        f"請使用python版本為3.9以上"
    )
class Win_Login(QMainWindow, Ui_LoginMainWindow):
    def __init__(self, parent=None):
        super(Win_Login, self).__init__(parent)
        self.setupUi(self)
        self.api_client = DesktopApiClient()
        self.setWindowIcon(QIcon('img/favicon.ico'))
        # 設置視窗大小
        self.resize(700, 450)
        # 設置視窗不可拖动
        self.setFixedSize(self.width(), self.height())
        # 設置視窗只显示关闭按钮
        self.setWindowFlags(Qt.WindowCloseButtonHint)
        # 隱藏邊框1
        self.setWindowFlags(Qt.FramelessWindowHint)

        self.close_btn.clicked.connect(self.to_close)
        self.btn_login.clicked.connect(self.onSignIn)
        self.btn_register.clicked.connect(self.to_register)
        self.edit_password.returnPressed.connect(self.onSignIn)
        self.min_btn.clicked.connect(self.min_window)
        self.edit_username.setPlaceholderText("请输入用户名或 Email")
        self.main_window = None
        # 背景图路径
        self.background = QPixmap("ui/UserLogin/img/登录.png")

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.drawPixmap(self.rect(), self.background)



    def onSignIn(self):
        # 获取用户名密码
        username = self.edit_username.text().strip()
        password = self.edit_password.text().strip()

        if username == "" or password == "":
            DialogOver(parent=self, text="用户名/密码不能为空", title="错误", flags="warning")
            return

        try:
            result = self.api_client.login(username, password)
        except ApiError as exc:
            DialogOver(parent=self, text=exc.message, title="错误", flags="warning")
            return

        user_info = result["user"]
        avatar_path = user_info.get("avatar") or ""
        avatar_url = user_info.get("avatar_url")
        _ensure_avatar_cached(self.api_client, avatar_path, avatar_url=avatar_url)
        nickname = user_info.get("nickname") or username
        register_time = self._format_register_time(user_info.get("register_time"))
        is_admin = user_info.get("is_admin", False)

        if is_admin == 1:
            # 如果是管理员，跳转到管理员界面
            from AdminMainUI import AdminWindow
            self.main_window = AdminWindow()
            admin_info_instance = UserInfo()
            # 清除另一角色的舊 session，避免下次啟動 restore 時角色錯亂
            admin_info_instance.clear_user_info()
            admin_info_instance.save_admin_user_info(username, nickname, avatar_path, register_time)
            admin_info_instance.save_admin_token(
                result.get("access_token", ""),
                result.get("token_type", "bearer"),
            )
        else:
            # 将用户信息保存到 UserInfo
            user_info_instance = UserInfo()
            # 清除另一角色的舊 session，避免下次啟動 restore 時角色錯亂
            user_info_instance.clear_admin_user_info()
            user_info_instance.save_user_info(username, nickname, avatar_path, register_time)
            user_info_instance.save_user_token(
                result.get("access_token", ""),
                result.get("token_type", "bearer"),
            )
            from MainUI import Client
            self.main_window = Client()
            self.main_window.set_userinfo()

        self.main_window.show()
        self.hide()
        self.edit_username.setText("")
        self.edit_password.setText("")

    def to_register(self):
        SI.registerWin = RegisterClient()
        SI.registerWin.show()
        self.hide()

    def min_window(self):
        self.showMinimized()

    def to_close(self):
        self.close()

    @staticmethod
    def _format_register_time(register_time):
        if not register_time:
            return ""
        try:
            return datetime.datetime.fromisoformat(
                str(register_time).replace("Z", "+00:00")
            ).strftime('%Y-%m-%d')
        except ValueError:
            return str(register_time)


def _ensure_avatar_cached(api_client, avatar_filename, avatar_url=None):
    """Download the backend avatar into the local user_avatars/ cache.

    Without this, a login on a new machine (or after cache loss) leaves the
    avatar blank because set_avatar() only reads from the local cache.
    """
    if not avatar_filename or "/" in avatar_filename or "\\" in avatar_filename:
        return
    target = os.path.join("user_avatars", avatar_filename)
    if os.path.exists(target):
        return
    source_url = avatar_url or f"/static/avatars/{avatar_filename}"
    try:
        data = api_client.fetch_binary(source_url)
    except ApiError:
        return
    os.makedirs("user_avatars", exist_ok=True)
    with open(target, "wb") as file_obj:
        file_obj.write(data)


def restore_saved_session():
    # Use a shorter timeout at startup so offline backend won't block UI for too long.
    api_client = DesktopApiClient(timeout=3)
    user_info = UserInfo()

    admin_token, _ = user_info.load_admin_token()
    if admin_token:
        try:
            admin_user = api_client.get_me(admin_token)
            if admin_user.get("is_admin"):
                _ensure_avatar_cached(
                    api_client,
                    admin_user.get("avatar") or "",
                    avatar_url=admin_user.get("avatar_url"),
                )
                user_info.save_admin_user_info(
                    admin_user.get("username", ""),
                    admin_user.get("nickname") or admin_user.get("username", ""),
                    admin_user.get("avatar") or "",
                    Win_Login._format_register_time(admin_user.get("register_time")),
                )
                from AdminMainUI import AdminWindow
                SI.mainWin = AdminWindow()
                SI.mainWin.show()
                return True
        except ApiError:
            pass
        user_info.clear_admin_user_info()

    user_token, _ = user_info.load_user_token()
    if user_token:
        try:
            normal_user = api_client.get_me(user_token)
            if not normal_user.get("is_admin"):
                _ensure_avatar_cached(
                    api_client,
                    normal_user.get("avatar") or "",
                    avatar_url=normal_user.get("avatar_url"),
                )
                user_info.save_user_info(
                    normal_user.get("username", ""),
                    normal_user.get("nickname") or normal_user.get("username", ""),
                    normal_user.get("avatar") or "",
                    Win_Login._format_register_time(normal_user.get("register_time")),
                )
                from MainUI import Client
                SI.mainWin = Client()
                SI.mainWin.show()
                return True
        except ApiError:
            pass
        user_info.clear_user_info()

    return False


if __name__ == '__main__':
    # Must be set before creating QApplication.
    # Avoid calling DPI helpers here because they may create a temporary QGuiApplication
    # and cause singleton conflicts when QApplication is created next.
    QGuiApplication.setHighDpiScaleFactorRoundingPolicy(
        Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
    )
    app = QApplication([])
    if not restore_saved_session():
        SI.loginWin = Win_Login()
        SI.loginWin.show()

    sys.exit(app.exec())
