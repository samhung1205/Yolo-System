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
from ui.admin.admin_edit_dialog import Ui_edit
from api_client import ApiError, DesktopApiClient
from avatar_cache import cache_avatar_file
from utils.UserInfo import UserInfo
USERNAME_RE = re.compile(r"^[A-Za-z0-9]{3,32}$")
EMAIL_RE = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]+$")
py_minor = sys.version_info.minor
if py_minor == 9:
    from utils.py39.main_utils import (
        save_avatar_file, upload_avatar, set_circular_avatar)
elif py_minor == 10:
    from utils.py310.main_utils import (
        save_avatar_file, upload_avatar, set_circular_avatar)
elif py_minor == 11:
    from utils.py311.main_utils import (
        save_avatar_file, upload_avatar, set_circular_avatar)
elif py_minor == 7:
    from utils.py37.main_utils import (
        save_avatar_file, upload_avatar, set_circular_avatar)
elif py_minor == 8:
    from utils.py38.main_utils import (
        save_avatar_file, upload_avatar, set_circular_avatar)
else:
    raise RuntimeError(
        f"请使用python版本为3.9"
    )

class EditUserWindow(QMainWindow, Ui_edit):
    user_updated = Signal()
    def __init__(self, user_id, username, email, nickname, avatar_filename, register_time,parent=None):
        super(EditUserWindow, self).__init__(parent)
        self.setupUi(self)  # 初始化界面
        self.api_client = DesktopApiClient()

        # 保存用户信息
        self.user_id = user_id
        self.username = username
        self.email = email
        self.nickname = nickname
        self.avatar_filename = avatar_filename
        self.set_avatar(avatar_filename)
        self.register_time = register_time
        self.label_edituser_avatar.mousePressEvent = self.upload_avatar
        self.upload_avatar_path = None  # 初始化头像文件路径
        self.configure_account_fields()
        self.init_ui()
        self.save_btn.clicked.connect(self.handleSubmit)
        self.cancel_btn.clicked.connect(self.close)



    def init_ui(self):
        # 将用户信息显示在对应的控件中
        self.edit_username.setText(self.username)
        self.edit_email.setText(self.email or "")
        self.edit_nickname.setText(self.nickname)

        register_time_str = self.register_time.strftime("%Y-%m-%d")  # 格式化时间为字
        self.user_register_time.setText(register_time_str)

    def configure_account_fields(self):
        self.resize(336, 500)
        self.email_label = QLabel("邮箱", self)
        self.email_label.setGeometry(30, 240, 54, 31)
        self.email_label.setAlignment(Qt.AlignCenter)

        self.edit_email = QLineEdit(self)
        self.edit_email.setObjectName("edit_email")
        self.edit_email.setGeometry(90, 240, 201, 31)
        self.edit_email.setClearButtonEnabled(True)
        self.edit_email.setPlaceholderText("请输入 Email")

        self.label.setGeometry(30, 290, 54, 31)
        self.edit_username.setGeometry(90, 290, 201, 31)
        self.edit_username.setPlaceholderText("请输入用户名")
        self.label_2.setGeometry(20, 340, 54, 31)
        self.user_register_time.setGeometry(90, 340, 201, 31)
        self.cancel_btn.setGeometry(90, 420, 71, 31)
        self.save_btn.setGeometry(180, 420, 71, 31)

    def upload_avatar(self, event):
        image_path = upload_avatar(self.label_edituser_avatar, circular=True)
        if image_path:
            self.upload_avatar_path = image_path  # 上传路径

    def set_avatar(self, avatar_filename):
        """设置头像并更新显示"""
        if avatar_filename:
            # 加载头像并设置到 QLabel
            avatar_path = os.path.join("user_avatars", avatar_filename)
            pixmap = QPixmap(avatar_path)
            if not pixmap.isNull():
                self.label_edituser_avatar.setPixmap(pixmap)
                set_circular_avatar(self.label_edituser_avatar)
        else:
            print("没有头像路径")



    def handleSubmit(self):
        """提交修改并更新数据库"""
        new_nickname = self.edit_nickname.text().strip()  # 获取昵称
        new_email = self.edit_email.text().strip().lower()  # 获取邮箱
        new_username  = self.edit_username.text().strip()  # 获取账号

        is_admin = 0

        if (
            not self.upload_avatar_path
            and self.nickname == new_nickname
            and self.username == new_username
            and (self.email or "") == new_email
        ):
            DialogOver(parent=self, text="未修改任何信息！", title="提交失败", flags="warning")
            return

        # 检查昵称和账号是否为空
        if len(new_username) == 0 or len(new_email) == 0 or len(new_nickname) == 0:
            DialogOver(parent=self, text="昵称、邮箱、账号不能为空", title="错误", flags="warning")
            return

        if not EMAIL_RE.match(new_email):
            DialogOver(parent=self, text="Email 格式错误", title="错误", flags="warning")
            return
        if not USERNAME_RE.match(new_username):
            DialogOver(parent=self, text="账号只能包含英文字母和数字，长度 3-32 位", title="错误", flags="warning")
            return

        user_info = UserInfo()
        access_token, _ = user_info.load_admin_token()
        if not access_token:
            DialogOver(parent=self, text="管理員登入資訊不存在，請重新登入", title="错误", flags="warning")
            return

        if not self.upload_avatar_path:
            avatar_filename = self.avatar_filename
        else:
            try:
                uploaded_avatar = self.api_client.upload_avatar(
                    access_token=access_token,
                    file_path=self.upload_avatar_path,
                )
            except ApiError as exc:
                DialogOver(parent=self, text=exc.message, title="错误", flags="warning")
                return
            avatar_filename = uploaded_avatar.get("filename", "")
            cache_avatar_file(self.upload_avatar_path, avatar_filename)

        try:
            self.api_client.update_user(
                access_token=access_token,
                user_id=self.user_id,
                username=new_username,
                email=new_email,
                nickname=new_nickname,
                is_admin=is_admin,
                avatar=avatar_filename,
            )
        except ApiError as exc:
            DialogOver(parent=self, text=exc.message, title="错误", flags="warning")
            return

        DialogOver(parent=self, text="修改已保存！", title="提交成功", flags="success")
        self.user_updated.emit()
        self.hide()

