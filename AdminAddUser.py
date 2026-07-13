# -*- coding: utf-8 -*-
"""
@Auth ：落花不写码
@File ：AdminAddUser.py
@IDE ：PyCharm
@Motto :学习新思想，争做新青年
"""
import os
import re
import sys
import datetime

from PySide6.QtCore import Signal

from utils.message import DialogOver

sys.path.append('ui/admin')
sys.path.append('desktop-app')
from PySide6.QtGui import QIcon, Qt, QPalette, QBrush, QPixmap, QGuiApplication, QColor
from PySide6.QtWidgets import QMainWindow, QMessageBox, QApplication, QFileDialog, QLabel, QLineEdit
from ui.admin.admin_add_dialog import Ui_add
from api_client import ApiError, DesktopApiClient
from avatar_cache import cache_avatar_file
from ui_state import SI
from utils.UserInfo import UserInfo

USERNAME_RE = re.compile(r"^[A-Za-z0-9]{3,32}$")
EMAIL_RE = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]+$")
PASSWORD_RE = re.compile(r"^(?=.*[A-Za-z])(?=.*\d)[A-Za-z\d]{8,64}$")

py_minor = sys.version_info.minor
if py_minor == 9:
    from utils.py39.main_utils import (
        save_avatar_file, upload_avatar, get_windows_scaling_factor, get_screen_resolution)
elif py_minor == 10:
    from utils.py310.main_utils import (
        save_avatar_file, upload_avatar, get_windows_scaling_factor, get_screen_resolution)
elif py_minor == 11:
    from utils.py311.main_utils import (
        save_avatar_file, upload_avatar, get_windows_scaling_factor, get_screen_resolution)
elif py_minor == 7:
    from utils.py37.main_utils import (
        save_avatar_file, upload_avatar, get_windows_scaling_factor, get_screen_resolution)
elif py_minor == 8:
    from utils.py38.main_utils import (
        save_avatar_file, upload_avatar, get_windows_scaling_factor, get_screen_resolution)
else:
    raise RuntimeError(
        f"请使用python版本为3.9"
    )

class AddUserWindow(QMainWindow, Ui_add):
    add_user_updated = Signal()
    def __init__(self, parent=None):
        super(AddUserWindow, self).__init__(parent)
        self.setupUi(self)  # 初始化界面
        self.api_client = DesktopApiClient()
        self.avatar_file_path = None  # 初始化头像文件路径
        self.label_adduser_avatar.mousePressEvent = self.upload_avatar
        self.save_btn.clicked.connect(self.save_data)
        self.cancel_btn.clicked.connect(self.close)
        self.configure_account_fields()




    def upload_avatar(self, event):
        """处理点击头像时上传头像"""
        # 上传头像并显示为带边框的头像
        image_path = upload_avatar(self.label_adduser_avatar, circular=False, border_width=30, border_color=QColor('#ffffff'))
        if image_path:
            self.avatar_file_path = image_path  # 保存文件路径

    def configure_account_fields(self):
        self.resize(336, 500)
        self.email_label = QLabel("邮箱", self)
        self.email_label.setGeometry(30, 240, 54, 31)
        self.email_label.setAlignment(Qt.AlignCenter)

        self.add_email = QLineEdit(self)
        self.add_email.setObjectName("add_email")
        self.add_email.setGeometry(90, 240, 201, 31)
        self.add_email.setClearButtonEnabled(True)
        self.add_email.setPlaceholderText("请输入 Email")

        self.label.setGeometry(30, 290, 54, 31)
        self.add_username.setGeometry(90, 290, 201, 31)
        self.add_username.setPlaceholderText("请输入用户名")
        self.label_2.setGeometry(30, 340, 54, 31)
        self.add_password.setGeometry(90, 340, 201, 31)
        self.add_password.setPlaceholderText("至少8位，包含英文与数字")
        self.cancel_btn.setGeometry(90, 420, 71, 31)
        self.save_btn.setGeometry(180, 420, 71, 31)

    def save_data(self):
        nick_nema = self.add_nickname.text().strip()
        email = self.add_email.text().strip().lower()
        username = self.add_username.text().strip()
        password = self.add_password.text().strip()
        if len(username) == 0 or len(email) == 0 or len(password) == 0  or len(nick_nema) == 0:
            DialogOver(parent=self, text="昵称、邮箱、账号、密码不能为空", title="错误", flags="warning")
            return
        if not EMAIL_RE.match(email):
            DialogOver(parent=self, text="Email 格式错误", title="错误", flags="warning")
            return
        if not USERNAME_RE.match(username):
            DialogOver(parent=self, text="账号只能包含英文字母和数字，长度 3-32 位", title="错误", flags="warning")
            return
        if not PASSWORD_RE.match(password):
            DialogOver(parent=self, text="密码必须至少 8 位，且同时包含英文与数字", title="错误", flags="warning")
            return

        # 检查头像是否上传
        if self.avatar_file_path is None:
            DialogOver(parent=self, text="请上传头像", title="错误", flags="warning")
            return

        else:
            user_info = UserInfo()
            access_token, _ = user_info.load_admin_token()
            if not access_token:
                DialogOver(parent=self, text="管理員登入資訊不存在，請重新登入", title="错误", flags="warning")
                return

            try:
                uploaded_avatar = self.api_client.upload_avatar(
                    access_token=access_token,
                    file_path=self.avatar_file_path,
                )
                avatar_filename = uploaded_avatar.get("filename", "")
                cache_avatar_file(self.avatar_file_path, avatar_filename)
                self.api_client.create_user(
                    access_token=access_token,
                    username=username,
                    email=email,
                    password=password,
                    nickname=nick_nema,
                    avatar=avatar_filename,
                )
            except ApiError as exc:
                DialogOver(parent=self, text=exc.message, title="错误", flags="warning")
                return

            DialogOver(parent=self, text="恭喜您添加成功", title="成功", flags="success")
            self.add_user_updated.emit()
            self.hide()





if __name__ == "__main__":
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
    app = QApplication([])
    SI.AddWindow = AddUserWindow()
    SI.AddWindow.show()
    sys.exit(app.exec())
