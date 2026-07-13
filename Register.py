# -*- coding: utf-8 -*-
"""
@Auth ： 落花不写码
@File ：login.py
@IDE ：PyCharm
@Motto:学习新思想，争做新青年
@Email ：179958974@qq.com
"""
import os
import sys
sys.path.append('ui/UserLogin')
sys.path.append('desktop-app')
import datetime
from PySide6.QtGui import QIcon, Qt, QPalette, QBrush, QPixmap, QGuiApplication, QColor, QPainter
from PySide6.QtWidgets import QMainWindow, QMessageBox, QApplication, QFileDialog, QLabel, QLineEdit

from api_client import ApiError, DesktopApiClient
from ui_state import SI
from ui.UserLogin.register import Ui_registerWindow as registerWindow
import re
from utils.message import DialogOver

USERNAME_RE = re.compile(r"^[A-Za-z0-9]{3,32}$")
EMAIL_RE = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]+$")
PASSWORD_RE = re.compile(r"^(?=.*[A-Za-z])(?=.*\d)[A-Za-z\d]{8,64}$")

py_minor = sys.version_info.minor
if py_minor == 9:
    from utils.py39.main_utils import (
        set_border_avatar, save_avatar_file, upload_avatar,get_windows_scaling_factor, get_screen_resolution)
elif py_minor == 10:
    from utils.py310.main_utils import (
        set_border_avatar, save_avatar_file, upload_avatar,get_windows_scaling_factor, get_screen_resolution)
elif py_minor == 11:
    from utils.py311.main_utils import (
        set_border_avatar, save_avatar_file, upload_avatar,get_windows_scaling_factor, get_screen_resolution)
elif py_minor == 7:
    from utils.py37.main_utils import (
        set_border_avatar, save_avatar_file, upload_avatar,get_windows_scaling_factor, get_screen_resolution)
elif py_minor == 8:
    from utils.py38.main_utils import (
        set_border_avatar, save_avatar_file, upload_avatar,get_windows_scaling_factor, get_screen_resolution)
else:
    raise RuntimeError(
        f"请使用python版本为3.9"
    )

# 登录
class RegisterClient(QMainWindow,registerWindow):
    def __init__(self):
        super(RegisterClient, self).__init__()
        self.setupUi(self)
        self.api_client = DesktopApiClient()
        #self.setWindowIcon(QIcon('img/favicon.ico'))
        # 设置窗口大小
        self.resize(700, 450)
        # 设置窗口不可拖动
        self.setFixedSize(self.width(), self.height())
        # 设置窗口只显示关闭按钮
        self.setWindowFlags(Qt.WindowCloseButtonHint)
        # 隐藏边框
        self.setWindowFlags(Qt.FramelessWindowHint)
        self.close_btn.clicked.connect(QApplication.quit)
        self.register_btn.clicked.connect(self.onRegisterIn)
        self.min_btn.clicked.connect(self.min_window)
        self.back_btn.clicked.connect(self.back_login)
        self.label_register_avatar.mousePressEvent = self.upload_avatar
        self.avatar_file_path = None  # 初始化头像文件路径
        #self.main_window = Client()
        # 背景图路径
        self.background = QPixmap("ui/UserLogin/img/登录.png")
        self.configure_account_fields()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.drawPixmap(self.rect(), self.background)

    def min_window(self):
        self.showMinimized()

    # 注册页面返回功能
    def back_login(self):
        self.hide()
        SI.loginWin.show()

    def upload_avatar(self, event):
        """处理点击头像时上传头像"""
        # 上传头像并显示为带边框的头像
        image_path = upload_avatar(self.label_register_avatar, circular=False, border_width=30, border_color=QColor('#ffffff'))
        if image_path:
            self.avatar_file_path = image_path  # 保存文件路径

    def configure_account_fields(self):
        self.resize(700, 500)
        self.setFixedSize(self.width(), self.height())

        self.register_email = QLineEdit(self.mainWindow)
        self.register_email.setObjectName("register_email")
        self.register_email.setGeometry(230, 224, 201, 31)
        self.register_email.setClearButtonEnabled(True)
        self.register_email.setPlaceholderText("请输入 Email")

        self.email_label = QLabel("邮箱", self.mainWindow)
        self.email_label.setGeometry(160, 224, 51, 31)
        self.email_label.setAlignment(Qt.AlignCenter)

        self.register_username.setGeometry(230, 274, 201, 31)
        self.register_username.setPlaceholderText("请输入用户名")
        self.register_password.setGeometry(230, 324, 201, 31)
        self.register_password.setPlaceholderText("至少8位，包含英文与数字")
        self.again_password.setGeometry(230, 374, 201, 31)
        self.register_btn.setGeometry(230, 430, 201, 31)
        self.label.setGeometry(440, 330, 220, 21)
        self.label.setText(" 密码至少8位，且需包含英文与数字")

        self.logo1.setGeometry(190, 280, 21, 21)
        self.logo2.setGeometry(190, 330, 21, 21)
        self.logo3.setGeometry(190, 374, 21, 21)


    def onRegisterIn(self):
        # 获取用户名密码 去除前后误输入空格
        nick_nema = self.register_nickname.text().strip()
        email = self.register_email.text().strip().lower()
        username = self.register_username.text().strip()
        password = self.register_password.text().strip()
        ack_psd = self.again_password.text().strip()
        if len(username) == 0 or len(email) == 0 or len(password) == 0 or len(ack_psd) == 0 or len(nick_nema) == 0:
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


        if str(password) != str(ack_psd):
            DialogOver(parent=self, text="两次输入密码不一致", title="错误", flags="warning")
            return
        # 检查头像是否上传
        if self.avatar_file_path is None:
            DialogOver(parent=self, text="请上传头像", title="错误", flags="warning")
            return

        else:
            try:
                self.api_client.register(username, email, password, nick_nema)
            except ApiError as exc:
                DialogOver(parent=self, text=exc.message, title="错误", flags="warning")
                return

            DialogOver(parent=self, text="恭喜您注册成功", title="成功", flags="success")
            SI.loginWin.show()
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
    SI.Ui_registerWindow = RegisterClient()
    SI.Ui_registerWindow.show()
    sys.exit(app.exec())
