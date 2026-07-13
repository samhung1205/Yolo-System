# -*- coding: utf-8 -*-
"""
@Auth ：落花不写码
@File ：AdminMainUI.py
@IDE ：PyCharm
@Motto :学习新思想，争做新青年
"""
import os
import re
import sys
import datetime
from utils.UserInfo import UserInfo
from utils.message import DialogOver
sys.path.append('ui/admin')
sys.path.append('desktop-app')
from PySide6.QtWidgets import QApplication, QMainWindow, QFileDialog, QMenu, QTableWidgetItem, QHeaderView, QDialog, \
    QGraphicsDropShadowEffect, QCheckBox, QHBoxLayout, QWidget, QLabel, QPushButton
from PySide6.QtGui import QImage, QPixmap, QColor, QCursor, QAction, QGuiApplication, QPainter, QPainterPath, QIcon
from PySide6.QtCore import QTimer, QThread, Signal, QObject, Qt, QEvent
from ui.admin.admin_ui_v2 import Ui_MainWindow as AdminMainWindow
from api_client import ApiError, DesktopApiClient
from avatar_cache import cache_avatar_file
from ui_state import SI
py_minor = sys.version_info.minor
if py_minor == 9:
    from utils.py39.main_utils import (
        set_circular_avatar, save_avatar_file, upload_avatar,get_windows_scaling_factor, get_screen_resolution)
elif py_minor == 10:
    from utils.py310.main_utils import (
        set_circular_avatar, save_avatar_file, upload_avatar,get_windows_scaling_factor, get_screen_resolution)
elif py_minor == 11:
    from utils.py311.main_utils import (
        set_circular_avatar, save_avatar_file, upload_avatar,get_windows_scaling_factor, get_screen_resolution)
elif py_minor == 7:
    from utils.py37.main_utils import (
        set_circular_avatar, save_avatar_file, upload_avatar,get_windows_scaling_factor, get_screen_resolution)
elif py_minor == 8:
    from utils.py38.main_utils import (
        set_circular_avatar, save_avatar_file, upload_avatar,get_windows_scaling_factor, get_screen_resolution)
else:
    raise RuntimeError(
        f"请使用python版本为3.9"
    )




class AdminWindow(QMainWindow, AdminMainWindow):
    def __init__(self, parent=None):
        super(AdminWindow, self).__init__()
        self.setupUi(self)  # 初始化界面
        self.api_client = DesktopApiClient()
        self.data = []
        self.center_window()  # 居中显示窗口
        self.fetch_data()
        self.set_table_row_count()
        self.user_tableWidget.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.emit_signal()
        self.set_button_icons_color(QColor(255, 255, 255))  # 设置按钮的图标颜色
        self.apply_button_styles()
        self.index_btn.setCheckable(True)
        self.user_manage_btn.setCheckable(True)
        self.admin_info_btn.setCheckable(True)
        self.index_btn.setChecked(True)
        self.show_home()  # 确保启动时显示首页
        self.update_button_styles()
        self.set_admin_user_info()
        self.upload_avatar_path = None  # 初始化头像文件路径
        self.label_avatar.mousePressEvent = self.upload_avatar


    def emit_signal(self):
        self.index_btn.clicked.connect(self.show_home)
        self.user_manage_btn.clicked.connect(self.show_user_manage)
        self.admin_info_btn.clicked.connect(self.show_profile)
        self.select_pushButton.clicked.connect(self.search_data)
        self.delete_pushButton.clicked.connect(self.delete_selected_rows)
        self.user_tableWidget.cellClicked.connect(self.on_cell_clicked)
        self.add_pushButton.clicked.connect(self.add_user)
        self.exit_btn.clicked.connect(self.to_close)
        self.handleSubmit_btn.clicked.connect(self.handleSubmit)
        self.handleClose_btn.clicked.connect(self.handleClose)
        self.handleSubmit_btn_password.clicked.connect(self.handleSubmit_password)




    def set_admin_user_info(self):
        user_info = UserInfo()
        username, nickname, avatar_path,register_time = user_info.load_admin_user_info()
        self.pushButton_mian_username.setText(nickname)  # 显示昵称
        self.lineEdit_name.setText(nickname)
        self.lineEdit_phone.setText(username)
        self.lineEdit_createTime.setText(register_time)
        self.lineEdit_phone.setDisabled(True)
        self.lineEdit_createTime.setDisabled(True)
        if avatar_path:
            self.set_avatar(avatar_path)


    def set_avatar(self, avatar_filename):
        """设置头像并更新显示"""
        if avatar_filename:
            # 加载头像并设置到 QLabel
            avatar_path = os.path.join("user_avatars", avatar_filename)
            pixmap = QPixmap(avatar_path)
            if not pixmap.isNull():
                self.label_userAvatar.setPixmap(pixmap)
                self.label_avatar.setPixmap(pixmap)
                labels = [self.label_userAvatar, self.label_avatar]
                for label in labels:
                    set_circular_avatar(label)
        else:
            print("没有头像路径")

    def set_button_icons_color(self, color: QColor):
        buttons = [self.index_btn, self.user_manage_btn, self.admin_info_btn, self.exit_btn]
        for button in buttons:
            button.setIcon(self.set_icon_color(button.icon(), color))

    # 设置图标颜色
    def set_icon_color(self, icon: QIcon, color: QColor) -> QIcon:
        pixmap = icon.pixmap(100, 100)
        painter = QPainter(pixmap)
        painter.setCompositionMode(QPainter.CompositionMode_SourceIn)
        painter.fillRect(pixmap.rect(), color)
        painter.end()
        return QIcon(pixmap)

    def apply_button_styles(self):
        # 鼠标悬停事件中动态改变图标颜色
        self.index_btn.installEventFilter(self)
        self.user_manage_btn.installEventFilter(self)
        self.admin_info_btn.installEventFilter(self)
        self.exit_btn.installEventFilter(self)

    # def eventFilter(self, source, event):
    #     if event.type() == QEvent.HoverEnter:
    #         if source == self.index_btn:
    #             self.index_btn.setIcon(self.set_icon_color(self.index_btn.icon(), QColor(0, 176, 240)))  # 修改图标颜色
    #         elif source == self.user_manage_btn:
    #             self.user_manage_btn.setIcon(self.set_icon_color(self.user_manage_btn.icon(), QColor(0, 176, 240)))
    #         elif source == self.admin_info_btn:
    #             self.admin_info_btn.setIcon(self.set_icon_color(self.admin_info_btn.icon(), QColor(0, 176, 240)))
    #         elif source == self.exit_btn:
    #             self.exit_btn.setIcon(self.set_icon_color(self.exit_btn.icon(), QColor(0, 176, 240)))
    #     elif event.type() == QEvent.HoverLeave:
    #         if source == self.index_btn:
    #             self.index_btn.setIcon(self.set_icon_color(self.index_btn.icon(), QColor(255, 255, 255)))  # 恢复原色
    #         elif source == self.user_manage_btn:
    #             self.user_manage_btn.setIcon(self.set_icon_color(self.user_manage_btn.icon(), QColor(255, 255, 255)))
    #         elif source == self.admin_info_btn:
    #             self.admin_info_btn.setIcon(self.set_icon_color(self.admin_info_btn.icon(), QColor(255, 255, 255)))
    #         elif source == self.exit_btn:
    #             self.exit_btn.setIcon(self.set_icon_color(self.exit_btn.icon(), QColor(255, 255, 255)))
    #     return super().eventFilter(source, event)

    def eventFilter(self, source, event):
        if event.type() == QEvent.HoverEnter:
            if source == self.index_btn:
                self.index_btn.setIcon(self.set_icon_color(self.index_btn.icon(), QColor(0, 176, 240)))  # 修改图标颜色
            elif source == self.user_manage_btn:
                self.user_manage_btn.setIcon(self.set_icon_color(self.user_manage_btn.icon(), QColor(0, 176, 240)))
            elif source == self.admin_info_btn:
                self.admin_info_btn.setIcon(self.set_icon_color(self.admin_info_btn.icon(), QColor(0, 176, 240)))
            elif source == self.exit_btn:
                self.exit_btn.setIcon(self.set_icon_color(self.exit_btn.icon(), QColor(0, 176, 240)))
        elif event.type() == QEvent.HoverLeave:
            if source == self.index_btn:
                if not self.index_btn.isChecked():
                    self.index_btn.setIcon(self.set_icon_color(self.index_btn.icon(), QColor(255, 255, 255)))
            elif source == self.user_manage_btn:
                if not self.user_manage_btn.isChecked():
                    self.user_manage_btn.setIcon(
                        self.set_icon_color(self.user_manage_btn.icon(), QColor(255, 255, 255)))
            elif source == self.admin_info_btn:
                if not self.admin_info_btn.isChecked():
                    self.admin_info_btn.setIcon(self.set_icon_color(self.admin_info_btn.icon(), QColor(255, 255, 255)))
            elif source == self.exit_btn:
                self.exit_btn.setIcon(self.set_icon_color(self.exit_btn.icon(), QColor(255, 255, 255)))
        return super().eventFilter(source, event)

    def update_button_styles(self):
        # 更新按钮的图标颜色
        buttons = [self.index_btn, self.user_manage_btn, self.admin_info_btn]
        for button in buttons:
            if button.isChecked():
                button.setIcon(self.set_icon_color(button.icon(), QColor(0, 176, 240)))
                button.setStyleSheet("color: rgb(96, 152, 234);")
            else:
                button.setIcon(self.set_icon_color(button.icon(), QColor(255, 255, 255)))
                button.setStyleSheet("")


    def show_home(self):
        self.stackedWidget.setCurrentIndex(0)
        self.index_btn.setChecked(True)
        self.user_manage_btn.setChecked(False)
        self.admin_info_btn.setChecked(False)
        self.update_button_styles()


    def show_user_manage(self):
        self.stackedWidget.setCurrentIndex(1)
        self.index_btn.setChecked(False)
        self.user_manage_btn.setChecked(True)
        self.admin_info_btn.setChecked(False)
        self.update_button_styles()

    def show_profile(self):
        self.stackedWidget.setCurrentIndex(2)
        self.index_btn.setChecked(False)
        self.user_manage_btn.setChecked(False)
        self.admin_info_btn.setChecked(True)
        self.update_button_styles()



    # def fetch_data(self, sql="select * from user order by register_time desc "):
    #     self.data = selectDB(sql)

    def fetch_data(self, account="", nickname=""):
        try:
            self.data = self._load_users_from_api(account=account, nickname=nickname)
        except ApiError as exc:
            self.data = []
            DialogOver(parent=self, text=exc.message, title="错误", flags="warning")

    def search_data(self):
        account = self.account_lineEdit.text().strip()
        nickname = self.nikename_lineEdit.text().strip()
        self.fetch_data(account=account, nickname=nickname)
        self.set_table_row_count()

    def set_table_row_count(self):
        self.user_tableWidget.setRowCount(len(self.data))

        row_height = 40  # 单元格高度
        for row in range(self.user_tableWidget.rowCount()):
            self.user_tableWidget.setRowHeight(row, row_height)

        # 设置表格内容并在第一列添加复选框
        for row, record in enumerate(self.data):
            # 在第一列插入复选框
            checkbox = QCheckBox()
            # 创建一个布局并将复选框放入该布局
            layout = QHBoxLayout()
            layout.setAlignment(Qt.AlignmentFlag.AlignCenter)  # 设置布局居中
            layout.addWidget(checkbox)

            cell_widget = QWidget()
            cell_widget.setLayout(layout)
            self.user_tableWidget.setCellWidget(row, 0, cell_widget)

            avatar_filename = record["avatar"] or ""
            avatar_path = os.path.join("user_avatars", avatar_filename)  # 拼接路径

            # 创建QLabel用于显示头像
            avatar_label = QLabel()
            if os.path.exists(avatar_path):
                pixmap = QPixmap(avatar_path)
                avatar_label.setPixmap(pixmap)
                avatar_label.setScaledContents(True)  # 启用自动缩放
                # 如果你希望图片填充整个标签区域，可以设置QLabel的大小为你需要的固定大小
                avatar_label.setFixedSize(30, 28)  # 设置QLabel固定大小
            else:
                avatar_label.setText("No Avatar")  # 如果没有头像，则显示文字提示

            # 创建一个布局并将头像放入该布局
            avatar_layout = QHBoxLayout()
            avatar_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)  # 设置布局居中
            avatar_layout.addWidget(avatar_label)

            # 创建一个QWidget并设置该布局
            avatar_cell_widget = QWidget()
            avatar_cell_widget.setLayout(avatar_layout)

            self.user_tableWidget.setCellWidget(row, 2, avatar_cell_widget)  # 第三列显示头像

            fields = ["id", "username", "nick_name"]
            columns = [1, 3, 4]
            for col, field, in zip(columns, fields):
                item = QTableWidgetItem(str(record[field]))
                self.user_tableWidget.setItem(row, col, item)
                # 设置每个单元格的对齐方式为居中
                item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)

            self.user_tableWidget.setCellWidget(row, 5, self.add_buttons_to_cell())



    def add_buttons_to_cell(self):
        widget = QWidget()
        # 修改
        self.edit_button = QPushButton('修改')
        self.edit_button.setStyleSheet('''
            QPushButton {
                text-align: center;
                background-color: rgb(92, 186, 48);
                color: rgb(255, 255, 255);
                height: 25px;
                border-radius: 3px;
                border-style: outset;
                font: 11px;
            }
            QPushButton:hover {
                
                background-color: rgb(112, 201, 74);
            }
        ''')

        # 删除
        self.delete_button = QPushButton('删除')
        self.delete_button.setStyleSheet('''
            QPushButton {
                text-align: center;
                background-color: rgb(240, 97, 95);
                color: rgb(255, 255, 255);
                height: 25px;
                border-radius: 3px;
                border-style: outset;
                font: 11px;
            }
            QPushButton:hover {
                background-color: rgb(240, 125, 122);
            }
        ''')

        self.edit_button.clicked.connect(self.edit_user)
        self.delete_button.clicked.connect(self.delete_row)

        hLayout = QHBoxLayout()
        hLayout.addWidget(self.edit_button)
        hLayout.addWidget(self.delete_button)
        hLayout.setContentsMargins(8, 2, 8, 2)
        widget.setLayout(hLayout)
        return widget
    def add_user(self):
        from AdminAddUser import AddUserWindow
        self.add_window = AddUserWindow(self)
        self.add_window.add_user_updated.connect(self.refresh_table)
        self.add_window.show()



    def edit_user(self):
        # 获取当前点击的按钮
        button = self.sender()
        if button:
            from AdminEditUser import EditUserWindow
            # 获取按钮所在的行
            row = self.user_tableWidget.indexAt(button.parent().pos()).row()
            # 获取用户信息
            user_id = self.user_tableWidget.item(row, 1).text()  # 用户ID
            username = self.user_tableWidget.item(row, 3).text()  # 账号
            nickname = self.user_tableWidget.item(row, 4).text()  # 昵称
            email = self.data[row].get("email")
            avatar_filename = self.data[row]["avatar"]
            register_time = self.data[row]["register_time"]
            # SI.EditWindow = EditUserWindow(user_id, username, nickname, avatar_filename, register_time)
            # SI.EditWindow.show()
            self.edit_window = EditUserWindow(user_id, username, email, nickname, avatar_filename, register_time, self)
            self.edit_window.user_updated.connect(self.refresh_table)
            self.edit_window.show()

    def refresh_table(self):
        self.fetch_data()
        self.set_table_row_count()

    # def delete_row(self):
    #     button = self.sender()
    #     if button:
    #         row = self.user_tableWidget.indexAt(button.parent().pos()).row()
    #         self.user_tableWidget.removeRow(row)

    def delete_row(self):
        """删除当前行的用户"""
        button = self.sender()
        if button:
            # 获取按钮所在的行
            row = self.user_tableWidget.indexAt(button.parent().pos()).row()
            # 获取用户 ID
            user_id = self.user_tableWidget.item(row, 1).text()  # 用户 ID 在第 1 列

            try:
                self.delete_from_api(user_id)
            except ApiError as exc:
                DialogOver(parent=self, text=exc.message, title="错误", flags="warning")
                return
            # 从表格中移除该行
            self.user_tableWidget.removeRow(row)
            DialogOver(parent=self, text="用户删除成功！", title="成功", flags="success")
            del self.data[row]  # 从数据源中删除该记录
            self.set_table_row_count()  # 更新表格行数




    def delete_selected_rows(self):
        rows_to_delete = []
        # 遍历每一行
        for row in range(self.user_tableWidget.rowCount()):
            checkbox = self.user_tableWidget.cellWidget(row, 0).findChild(QCheckBox)
            if checkbox and checkbox.isChecked():  # 如果复选框被选中
                rows_to_delete.append(row)

        # 从后往前删除行
        for row in reversed(rows_to_delete):
            record_id = self.user_tableWidget.item(row, 1).text()  # 取第二列id
            try:
                self.delete_from_api(record_id)  # 从后端删除该记录
            except ApiError as exc:
                DialogOver(parent=self, text=exc.message, title="错误", flags="warning")
                return
            del self.data[row]  # 从数据源中删除该记录
            self.user_tableWidget.removeRow(row)  # 从表格中删除该行

        self.set_table_row_count()  # 更新表格行数

    def delete_from_api(self, record_id):
        access_token = self._get_admin_access_token()
        self.api_client.delete_user(access_token=access_token, user_id=record_id)



    def on_cell_clicked(self, row, column):
        # 只在第一列点击时切换复选框的选中状态
        if column == 0:
            checkbox = self.user_tableWidget.cellWidget(row, 0).findChild(QCheckBox)
            if checkbox:
                checkbox.setChecked(not checkbox.isChecked())  # 切换复选框状态

    def upload_avatar(self, event):
        image_path = upload_avatar(self.label_avatar, circular=True)
        if image_path:
            self.upload_avatar_path = image_path  # 上传路径
    def handleSubmit(self):
        """提交修改并更新数据库"""
        new_nickname = self.lineEdit_name.text().strip()  # 获取昵称

        user_info = UserInfo()
        username, nickname, avatar_path, register_time = user_info.load_admin_user_info()  # 获取用户名和注册时间


        if not new_nickname:
            DialogOver(parent=self, text="昵称不能为空！", title="提交失败", flags="warning")
            return
        if not self.upload_avatar_path and nickname == new_nickname:
            DialogOver(parent=self, text="未修改任何信息！", title="提交失败", flags="warning")
            return
        if not self.upload_avatar_path:
            avatar_filename = avatar_path
        else:
            try:
                uploaded_avatar = self.api_client.upload_avatar(
                    access_token=self._get_admin_access_token(),
                    file_path=self.upload_avatar_path,
                )
            except ApiError as exc:
                DialogOver(parent=self, text=exc.message, title="提交失败", flags="warning")
                return
            avatar_filename = uploaded_avatar.get("filename", "")
            cache_avatar_file(self.upload_avatar_path, avatar_filename)

        try:
            current_admin = self._get_current_admin_user()
            self.api_client.update_user(
                access_token=self._get_admin_access_token(),
                user_id=current_admin["id"],
                nickname=new_nickname,
                avatar=avatar_filename,
            )
        except ApiError as exc:
            DialogOver(parent=self, text=exc.message, title="提交失败", flags="warning")
            return

        user_info.save_admin_user_info(username, new_nickname, avatar_filename, register_time)
        self.set_admin_user_info()  # 更新界面
        DialogOver(parent=self, text="修改已保存！", title="提交成功", flags="success")

    def handleSubmit_password(self):
        old_password = self.lineEdit_old_password.text().strip()
        new_password = self.lineEdit_new_password.text().strip()
        check_password = self.lineEdit_check_password.text().strip()


        ret_psd = re.match("^(?![A-Za-z]+$)(?![A-Z0-9]+$)(?![a-z0-9]+$)(?![a-z\W]+$)(?![A-Z\W]+$)(?![0-9\W]+$)[a-zA-Z0-9\W]{6,16}$",new_password)

        if not ret_psd:
            DialogOver(parent=self, text="密码不符合要求，必须包含字母、数字、特殊字符", title="错误", flags="warning")
            return

        if str(new_password) != str(check_password):
            DialogOver(parent=self, text="两次输入密码不一致", title="错误", flags="warning")
            return

        user_info = UserInfo()
        username, _, _, _ = user_info.load_admin_user_info()  # 获取账号
        try:
            self.api_client.login(username, old_password)
        except ApiError:
            DialogOver(parent=self, text="原密码不正确", title="错误", flags="warning")
            return

        try:
            current_admin = self._get_current_admin_user()
            self.api_client.update_user(
                access_token=self._get_admin_access_token(),
                user_id=current_admin["id"],
                password=new_password,
            )
        except ApiError as exc:
            DialogOver(parent=self, text=exc.message, title="错误", flags="warning")
            return

        self.lineEdit_old_password.setText("")
        self.lineEdit_new_password.setText("")
        self.lineEdit_check_password.setText("")
        DialogOver(parent=self, text="密码修改成功，下次登录生效！", title="成功", flags="success")



    def handleClose(self):
        self.set_admin_user_info()

    def center_window(self):
        screen = QGuiApplication.primaryScreen().availableGeometry()
        size = self.geometry()
        self.move((screen.width() - size.width()) / 2, (screen.height() - size.height()) / 2)

    def to_close(self):
        # 登出：清除 admin session（token + 個資），否則下次啟動會被
        # restore_saved_session() 自動還原成管理員介面
        UserInfo().clear_admin_user_info()
        self.hide()
        if not hasattr(SI, 'loginWin') or SI.loginWin is None:
            from Login import Win_Login
            SI.loginWin = Win_Login()
        SI.loginWin.show()
       #self.close()

    def _load_users_from_api(self, account="", nickname=""):
        access_token = self._get_admin_access_token()
        users = []
        page = 1
        limit = 100

        while True:
            response = self.api_client.list_users(access_token=access_token, page=page, limit=limit)
            items = response.get("items", [])
            if not items:
                break

            users.extend(items)
            if len(items) < limit:
                break
            page += 1

        filtered_users = []
        for item in users:
            if item.get("is_admin"):
                continue
            username = item.get("username", "")
            user_nickname = item.get("nickname") or ""
            if account and account not in username:
                continue
            if nickname and nickname not in user_nickname:
                continue
            filtered_users.append(self._normalize_user_record(item))

        filtered_users.sort(key=lambda record: record["register_time"], reverse=True)
        return filtered_users

    @staticmethod
    def _get_admin_access_token():
        user_info = UserInfo()
        access_token, _ = user_info.load_admin_token()
        if not access_token:
            raise ApiError("管理員登入資訊不存在，請重新登入")
        return access_token

    def _get_current_admin_user(self):
        return self.api_client.get_me(self._get_admin_access_token())

    @staticmethod
    def _normalize_user_record(item):
        register_time = item.get("register_time")
        if isinstance(register_time, str):
            try:
                register_time = datetime.datetime.fromisoformat(
                    register_time.replace("Z", "+00:00")
                )
                if register_time.tzinfo is not None:
                    register_time = register_time.astimezone(datetime.timezone.utc).replace(tzinfo=None)
            except ValueError:
                register_time = datetime.datetime.min
        elif register_time is None:
            register_time = datetime.datetime.min

        nickname = item.get("nickname") or ""
        return {
            "id": item.get("id"),
            "username": item.get("username", ""),
            "nickname": nickname,
            "nick_name": nickname,
            "avatar": item.get("avatar") or "",
            "register_time": register_time,
            "is_admin": item.get("is_admin", False),
        }





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
    app = QApplication(sys.argv)
    Home = AdminWindow()
    Home.show()
    sys.exit(app.exec())
