import json
import os
import re
import sys
import time
sys.path.append('ui')
sys.path.append('ui/UserInfo')
sys.path.append('desktop-app')
import cv2
import numpy as np
from PIL.Image import Image
from PySide6.QtWidgets import QApplication, QMainWindow, QFileDialog, QMenu, QTableWidgetItem, QHeaderView, QDialog, \
    QGraphicsDropShadowEffect, QPushButton, QVBoxLayout, QHBoxLayout, QLabel, QTableWidget, QComboBox
from PySide6.QtGui import QImage, QPixmap, QColor, QCursor, QAction, QGuiApplication, QPainter, QPainterPath, \
    QDesktopServices
from PySide6.QtCore import QTimer, QThread, Signal, QObject, Qt,QEvent, QUrl
from api_client import ApiError, DesktopApiClient
from avatar_cache import cache_avatar_file
from ui_state import SI
from utils.capnums import Camera
from detect_mainui import YoloPredictor
from ui.main_ui_v7 import Ui_MainWindow
from utils.UserInfo import UserInfo
from utils.message import DialogOver
from PersonFormMain import PersonFormMain
py_minor = sys.version_info.minor
if py_minor == 9:
    from utils.py39.main_utils import (
        set_circular_avatar, upload_avatar, save_avatar_file,check_url,get_windows_scaling_factor, get_screen_resolution)
elif py_minor == 10:
    from utils.py310.main_utils import (
        set_circular_avatar, upload_avatar, save_avatar_file,check_url,get_windows_scaling_factor, get_screen_resolution)
elif py_minor == 11:
    from utils.py311.main_utils import (
        set_circular_avatar, upload_avatar, save_avatar_file,check_url,get_windows_scaling_factor, get_screen_resolution)
elif py_minor == 7:
    from utils.py37.main_utils import (
        set_circular_avatar, upload_avatar, save_avatar_file,check_url,get_windows_scaling_factor, get_screen_resolution)
elif py_minor == 8:
    from utils.py38.main_utils import (
        set_circular_avatar, upload_avatar, save_avatar_file,check_url,get_windows_scaling_factor, get_screen_resolution)
else:
    raise RuntimeError(
        f"請使用python版本为3.9"
    )



class Client(QMainWindow, Ui_MainWindow):
    main2yolo_begin_sgl = Signal()

    def __init__(self, parent=None):
        super(Client, self).__init__()

        self.setupUi(self)  # 初始化界面
        self.api_client = DesktopApiClient()
        self.m_flag = False
        self.setWindowFlags(Qt.FramelessWindowHint)  # 隐藏标题栏
        self.progressBar.setValue(0)
        self.yolo_init()
        self.add_detection_controls()
        self.main_function_bind()
        self.pushButton_start_stop.setCheckable(True)  # 将按钮设置为开关状态为真
        self.yolo_predict.new_model_name = os.getenv("YOLO_DESKTOP_MODEL", "yolo11n.pt")
        self.yolo_predict.load_yolo_model()
        self.tableWidget.verticalHeader().setSectionResizeMode(QHeaderView.Fixed)
        self.tableWidget.verticalHeader().setDefaultSectionSize(40)
        self.tableWidget.setColumnWidth(0, 80)
        self.tableWidget.setColumnWidth(1, 200)
        self.tableWidget.setColumnWidth(2, 150)
        self.tableWidget.setColumnWidth(3, 90)
        self.tableWidget.setColumnWidth(4, 230)
        self.tableWidget.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.tableWidget.horizontalHeader().setSectionResizeMode(1, QHeaderView.Interactive)

        self.center_window()  # 居中顯示視窗
        self.set_avatars()
        self.set_userinfo()
        self.person_form = None  # 初始化彈出視窗
        self.pushButton_mian_username.installEventFilter(self)  # 懸停事件
        self.installEventFilter(self)  # 主視窗的事件過濾器
        self.upload_avatar_path = None  # 初始化影像文件路徑
        self.current_detection = None
        self.history_dialog = None
        self._polling_cancelled = False  # 關窗時停止影片偵測輪詢

    def yolo_init(self):
        # Yolo-v8 thread  初始化
        self.yolo_predict = YoloPredictor()
        self.yolo_thread = QThread()
        self.yolo_predict.yolo2main_trail_img.connect(lambda x: self.show_image(x, self.label_input, 'img'))  # 绑定原始图
        self.yolo_predict.yolo2main_box_img.connect(lambda x: self.show_image(x, self.label_out, 'img'))  # 绑定结果图
        self.yolo_predict.yolo2main_status_msg.connect(lambda x: self.show_status(x))
        self.yolo_predict.yolo2main_tabel_show.connect(self.tabel_show)
        self.yolo_predict.yolo2main_progressBar.connect(lambda x: self.progressBar.setValue(x))  # 进度条
        # 将主线程的信号绑定到 Yolo 类的槽函数上，并启动 Yolo 线程
        self.yolo_predict.moveToThread(self.yolo_thread)
        self.main2yolo_begin_sgl.connect(self.yolo_predict.run)

    # 主页面各功能绑定
    def main_function_bind(self):
        # 打开文件夹
        self.pushButton_openimg.clicked.connect(self.open_src_file)
        # 摄像头
        self.pushButton_sht.clicked.connect(self.chose_cam)
        # 开始
        self.pushButton_start_stop.clicked.connect(self.run_or_continue)
        # 终止
        self.pushButton_exit.clicked.connect(self.stop)

        self.min_btn.clicked.connect(self.to_minmal)
        self.max_btn.clicked.connect(self.max_or_restore)
        self.close_btn.clicked.connect(self.to_close)
        self.index_btn.clicked.connect(self.show_home)
        self.main_btn.clicked.connect(self.show_detect)
        self.userinfo_btn.clicked.connect(self.show_profile)
        self.index_btn.setCheckable(True)
        self.main_btn.setCheckable(True)
        self.userinfo_btn.setCheckable(True)

        # 设置默认选中的按钮和显示首页
        self.index_btn.setChecked(True)
        self.show_home()  # 确保启动时显示首页
        self.update_button_styles()
        self.label_avatar.mousePressEvent = self.upload_avatar
        self.exit_btn.clicked.connect(self.to_close)

        self.handleSubmit_btn.clicked.connect(self.handleSubmit)
        self.handleClose_btn.clicked.connect(self.handleClose)
        self.handleSubmit_btn_password.clicked.connect(self.handleSubmit_password)
        self.pushButton_history.clicked.connect(self.show_detection_history)
        self.pushButton_open_result.clicked.connect(self.open_current_result)
        self.pushButton_agent.clicked.connect(self.open_agent_window)

    def add_detection_controls(self):
        self.pushButton_history = QPushButton("歷史紀錄", self.frame_11)
        self.pushButton_history.setMaximumSize(101, 30)
        self.gridLayout_2.addWidget(self.pushButton_history, 0, 4, 1, 1)

        self.pushButton_open_result = QPushButton("打開結果", self.frame_11)
        self.pushButton_open_result.setMaximumSize(101, 30)
        self.gridLayout_2.addWidget(self.pushButton_open_result, 0, 5, 1, 1)

        # Phase 6A-3 — open standalone Agent Console for the current detection
        self.pushButton_agent = QPushButton("AI Agent", self.frame_11)
        self.pushButton_agent.setMaximumSize(101, 30)
        self.gridLayout_2.addWidget(self.pushButton_agent, 0, 6, 1, 1)


    def set_userinfo(self):
        user_info = UserInfo()
        username, nickname, avatar_path,register_time = user_info.load_user_info()
        self.pushButton_mian_username.setText(nickname)  # 顯示名稱
        self.lineEdit_name.setText(nickname)
        self.lineEdit_phone.setText(username)
        self.lineEdit_createTime.setText(register_time)
        self.lineEdit_phone.setDisabled(True)
        self.lineEdit_createTime.setDisabled(True)
        if avatar_path:
            self.set_avatar(avatar_path)

    def eventFilter(self, source, event):
        if source == self.pushButton_mian_username:
            if event.type() == QEvent.Enter:  # 滑鼠進入按鈕
                self.show_person_form()  # 顯示個人中心視窗
            elif event.type() == QEvent.Leave:  # 滑鼠離開按鈕
                # 判断滑鼠是否在彈出視窗區域内
                if self.person_form and not self.person_form.rect().contains(
                        self.person_form.mapFromGlobal(QCursor.pos())):
                    self.close_person_form()  # 關閉個人中心視窗

        elif source == self.person_form:
            if event.type() == QEvent.Enter:  # 鼠标进入弹出窗口时
                return True  # 允许事件继续传播

            if event.type() == QEvent.Leave:  # 鼠标离开弹出窗口时
                if not self.pushButton_mian_username.rect().contains(
                        self.pushButton_mian_username.mapFromGlobal(QCursor.pos())):
                    self.close_person_form()

        return super().eventFilter(source, event)
    def show_person_form(self):
        if not self.person_form:
            self.person_form = PersonFormMain(self)
            self.person_form.logout_signal.connect(self.logout)
            self.person_form.userinfo_signal.connect(self.show_profile)

            button_rect = self.pushButton_mian_username.geometry()
            x = button_rect.x()
            y = button_rect.bottom()

            # 设置弹出窗口的位置,位置这个自己调一下
            self.person_form.setGeometry(x + 70, y + 21, self.person_form.width(), self.person_form.height())

            self.person_form.setWindowFlags(Qt.FramelessWindowHint)  # 隐藏标题栏

            self.person_form.setWindowModality(Qt.ApplicationModal)  # 阻止父窗口交互

            # 弹出窗口事件过滤器
            self.person_form.installEventFilter(self)

            self.shadow_effect(self.person_form)


        if not self.person_form.isVisible():
            self.person_form.show()

    def close_person_form(self):
        if self.person_form and self.person_form.isVisible():
            self.person_form.close()
            self.person_form = None
    def shadow_effect(self, widget):
        shadow_effect = QGraphicsDropShadowEffect(widget)
        shadow_effect.setBlurRadius(15)  # 模糊半径
        shadow_effect.setColor(Qt.gray)  # 阴影颜色
        shadow_effect.setOffset(0, 0)

        # 将阴影应用到窗口
        widget.setGraphicsEffect(shadow_effect)

    def center_window(self):
        screen = QGuiApplication.primaryScreen().availableGeometry()
        size = self.geometry()
        self.move((screen.width() - size.width()) / 2, (screen.height() - size.height()) / 2)

    def set_avatars(self):
        labels = [self.label_userAvatar, self.label_avatar]
        for label in labels:
            set_circular_avatar(label)

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

    def handleSubmit(self):
        """提交修改并更新数据库"""
        new_nickname = self.lineEdit_name.text().strip()  # 获取昵称

        user_info = UserInfo()
        username, nickname, avatar_path, register_time = user_info.load_user_info()  # 获取用户名和注册时间


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
                    access_token=self._get_user_access_token(),
                    file_path=self.upload_avatar_path,
                )
            except ApiError as exc:
                DialogOver(parent=self, text=exc.message, title="提交失败", flags="warning")
                return
            avatar_filename = uploaded_avatar.get("filename", "")
            cache_avatar_file(self.upload_avatar_path, avatar_filename)

        try:
            current_user = self._get_current_user()
            self.api_client.update_user(
                access_token=self._get_user_access_token(),
                user_id=current_user["id"],
                nickname=new_nickname,
                avatar=avatar_filename,
            )
        except ApiError as exc:
            DialogOver(parent=self, text=exc.message, title="提交失败", flags="warning")
            return

        user_info.save_user_info(username, new_nickname, avatar_filename, register_time)
        self.set_userinfo()  # 更新界面
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
        username, _, _, _ = user_info.load_user_info()  # 获取账号
        try:
            self.api_client.login(username, old_password)
        except ApiError:
            DialogOver(parent=self, text="原密码不正确", title="错误", flags="warning")
            return

        try:
            current_user = self._get_current_user()
            self.api_client.update_user(
                access_token=self._get_user_access_token(),
                user_id=current_user["id"],
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
        self.set_userinfo()
    def logout(self):
        user_info_instance = UserInfo()
        user_info_instance.clear_user_info()
        self.hide()
        if not hasattr(SI, 'loginWin') or SI.loginWin is None:
            from Login import Win_Login
            SI.loginWin = Win_Login()
        SI.loginWin.show()

    def upload_avatar(self, event):
        image_path = upload_avatar(self.label_avatar, circular=True)
        if image_path:
            self.upload_avatar_path = image_path  # 上传路径

    def update_button_styles(self):
        # 更新按钮的背景颜色
        if self.index_btn.isChecked():
            self.index_btn.setStyleSheet("background:#e6e6e6; ")
        else:
            self.index_btn.setStyleSheet("")

        if self.main_btn.isChecked():
            self.main_btn.setStyleSheet("background:#e6e6e6;")
        else:
            self.main_btn.setStyleSheet("")

        if self.userinfo_btn.isChecked():
            self.userinfo_btn.setStyleSheet("background:#e6e6e6;")
        else:
            self.userinfo_btn.setStyleSheet("")

    @staticmethod
    def _get_user_access_token():
        user_info = UserInfo()
        access_token, _ = user_info.load_user_token()
        if not access_token:
            raise ApiError("使用者登入資訊不存在，請重新登入")
        return access_token

    def _get_current_user(self):
        return self.api_client.get_me(self._get_user_access_token())

    def show_home(self):
        self.stackedWidget.setCurrentIndex(0)
        self.index_btn.setChecked(True)
        self.main_btn.setChecked(False)
        self.userinfo_btn.setChecked(False)
        self.update_button_styles()

    def show_detect(self):
        self.stackedWidget.setCurrentIndex(1)
        self.index_btn.setChecked(False)
        self.main_btn.setChecked(True)
        self.userinfo_btn.setChecked(False)
        self.update_button_styles()
        self.refresh_latest_detection()

    def show_profile(self):
        self.stackedWidget.setCurrentIndex(2)
        self.index_btn.setChecked(False)
        self.main_btn.setChecked(False)
        self.userinfo_btn.setChecked(True)
        self.update_button_styles()

    #主窗口显示原图与检测结果
    @staticmethod
    def show_image(img, label, flag):

        if flag == "path":
            img_src = cv2.imdecode(np.fromfile(img, dtype=np.uint8), -1)
        else:
            img_src = img

        # Resize the image
        img_src_ = cv2.resize(img_src, (640, 480))

        # 将 OpenCV 图像转换为 QImage 对象，并将其显示在 QLabel 组件中
        frame = cv2.cvtColor(img_src_, cv2.COLOR_BGR2RGB)
        img = QImage(frame.data, frame.shape[1], frame.shape[0], frame.shape[2] * frame.shape[1], QImage.Format_RGB888)

        label.setPixmap(QPixmap.fromImage(img))
        label.setScaledContents(True)  # 自适应界面大小

    # 控制开始|暂停
    def run_or_continue(self):
        if self.yolo_predict.source == '' or self.yolo_predict.source is None:
            DialogOver(parent=self, text="请重新上传文件", title="运行失败", flags="danger")
            self.pushButton_start_stop.setChecked(False)
            return

        self.yolo_predict.stop_dtc = False
        # 开始
        if self.pushButton_start_stop.isChecked():
            if self.is_image_source():
                self.img_predict()
                return

            if self.is_local_video_source():
                self.video_predict()
                return

            # 视频预测
            self.pushButton_start_stop.setChecked(True)

            if '0' in self.yolo_predict.source or '1' in self.yolo_predict.source or 'rtsp' in self.yolo_predict.source:
                self.progressBar.setFormat('实时视频流检测中...')
            if 'avi' in self.yolo_predict.source or 'mp4' in self.yolo_predict.source:
                self.progressBar.setFormat('当前检测进度:%p%')
            self.yolo_predict.continue_dtc = True
            # 开始检测
            if not self.yolo_thread.isRunning():
                self.yolo_thread.start()
                self.main2yolo_begin_sgl.emit()
        # 暂停
        else:
            self.yolo_predict.continue_dtc = False
            self.pushButton_start_stop.setChecked(False)
            DialogOver(parent=self, text="暂停中...", title="运行暂停", flags="warning")

    # select local file
    def open_src_file(self):
        name, _ = QFileDialog.getOpenFileName(self, 'Video/image', '',
                                              "Pic File(*.mp4 *.mkv *.avi *.flv *.mov *.jpg *.png)")
        self.stop()
        if name:
            self.yolo_predict.source = name
            print('Loaded file：{}'.format(os.path.basename(name)))
            self.stop()
            if self.is_local_video_source(name):
                # 显示第一帧
                self.cap = cv2.VideoCapture(name)
                ret, frame = self.cap.read()
                if ret:
                    rgbImage = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                    self.show_image(rgbImage, self.label_input, 'img')

                else:
                    self.cap.release()
            else:
                self.show_image(name, self.label_input, 'path')

    def chose_cam(self):
        # try:
        # 关闭YOLO线程
        self.stop()
        # 获取本地摄像头数量
        _, cams = Camera().get_cam_num()
        popMenu = QMenu()
        popMenu.setFixedWidth(self.pushButton_sht.width())
        popMenu.setStyleSheet('''
                                            QMenu {
                                            font-size: 10px;
                                            font-family: "Microsoft YaHei UI";
                                            font-weight: light;
                                            color:white;
                                            padding-left: 5px;
                                            padding-right: 5px;
                                            padding-top: 4px;
                                            padding-bottom: 4px;
                                            border-style: solid;
                                            border-width: 0px;
                                            border-color: rgba(255, 212, 255, 255);
                                            border-radius: 3px;
                                            background-color: rgba(16,155,226,50);
                                            }
                                            ''')

        for cam in cams:
            exec("action_%s = QAction('%s 号摄像头')" % (cam, cam))
            exec("popMenu.addAction(action_%s)" % cam)
        pos = QCursor.pos()
        action = popMenu.exec(pos)

        # 设置摄像头来源
        if action:
            str_temp = ''
            selected_stream_source = str_temp.join(filter(str.isdigit, action.text()))  # 获取摄像头号，去除非数字字符
            self.yolo_predict.source = selected_stream_source




    def show_status(self, msg):
        if msg == '检测完成':
            self.pushButton_start_stop.setChecked(False)
            # 终止yolo线程
            if self.yolo_thread.isRunning():
                self.yolo_thread.quit()

        elif msg == '检测终止':
            self.pushButton_start_stop.setChecked(False)
            # 终止yolo线程
            if self.yolo_thread.isRunning():
                self.yolo_thread.quit()
            self.label_input.clear()
            self.label_out.clear()


    def stop(self):
        try:
            self.yolo_predict.release_capture()  # 终止使用摄像头
            # 结束线程
            self.yolo_thread.quit()

        except:
            pass

        self.yolo_predict.stop_dtc = True
        self.pushButton_start_stop.setChecked(False)  # 恢复按钮状态
        self.label_input.clear()  # 清空视频显示
        self.label_out.clear()  # 清空视频显示
        self.tableWidget.setRowCount(0)
        self.tableWidget.clearContents()
        self.progressBar.setValue(0)

    # 预测图片
    def img_predict(self):

        if check_url(self.yolo_predict.source):
            return

        self.pushButton_start_stop.setChecked(False)
        try:
            detection = self.api_client.detect_image(
                access_token=self._get_user_access_token(),
                file_path=self.yolo_predict.source,
                conf=self.yolo_predict.conf_thres,
                iou=self.yolo_predict.iou_thres,
            )
        except ApiError as exc:
            DialogOver(parent=self, text=exc.message, title="检测失败", flags="warning")
            self.yolo_predict.source = ''
            return

        try:
            self.render_detection_result(detection)
        except ApiError as exc:
            DialogOver(parent=self, text=exc.message, title="检测失败", flags="warning")
            self.yolo_predict.source = ''
            return

        self.yolo_predict.source = ''
        return

    def video_predict(self):
        if check_url(self.yolo_predict.source):
            return

        self.pushButton_start_stop.setChecked(False)
        self.progressBar.setFormat('视频检测中...')
        self.progressBar.setRange(0, 0)
        QApplication.processEvents()

        try:
            detection = self.api_client.detect_video(
                access_token=self._get_user_access_token(),
                file_path=self.yolo_predict.source,
                conf=self.yolo_predict.conf_thres,
                iou=self.yolo_predict.iou_thres,
            )
        except ApiError as exc:
            self.progressBar.setRange(0, 100)
            self.progressBar.setValue(0)
            self.progressBar.setFormat('当前检测进度:%p%')
            DialogOver(parent=self, text=exc.message, title="检测失败", flags="warning")
            self.yolo_predict.source = ''
            return

        try:
            detection = self.wait_for_detection_completion(detection["id"])
            self.render_detection_result(detection)
        except ApiError as exc:
            self.progressBar.setRange(0, 100)
            self.progressBar.setValue(0)
            self.progressBar.setFormat('当前检测进度:%p%')
            DialogOver(parent=self, text=exc.message, title="检测失败", flags="warning")
            self.yolo_predict.source = ''
            return

        self.progressBar.setRange(0, 100)
        self.progressBar.setFormat('当前检测进度:%p%')
        self.progressBar.setValue(100)
        self.yolo_predict.source = ''
        return

    def refresh_latest_detection(self):
        try:
            detections = self.api_client.list_detections(self._get_user_access_token())
        except ApiError:
            return

        if not detections:
            return

        latest_detection_id = detections[0].get("id")
        if latest_detection_id is None:
            return

        try:
            detection = self.api_client.get_detection(
                access_token=self._get_user_access_token(),
                detection_id=latest_detection_id,
            )
            self.render_detection_result(detection)
        except ApiError:
            return

    def render_detection_result(self, detection):
        self.current_detection = detection
        source_type = detection.get("source_type")
        preview_image_url = detection.get("preview_image_url")
        source_image_url = detection.get("source_image_url")
        if source_image_url:
            original_image = self.fetch_remote_image(source_image_url)
            if original_image is not None:
                self.show_image(original_image, self.label_input, 'img')
        elif source_type == "video" and preview_image_url:
            preview_image = self.fetch_remote_image(preview_image_url)
            if preview_image is not None:
                self.show_image(preview_image, self.label_input, 'img')

        result_image_url = detection.get("result_image_url")
        if result_image_url:
            result_image = self.fetch_remote_image(result_image_url)
            if result_image is not None:
                self.show_image(result_image, self.label_out, 'img')
            elif source_image_url:
                original_image = self.fetch_remote_image(source_image_url)
                if original_image is not None:
                    self.show_image(original_image, self.label_out, 'img')
        elif source_type == "video" and preview_image_url:
            preview_image = self.fetch_remote_image(preview_image_url)
            if preview_image is not None:
                self.show_image(preview_image, self.label_out, 'img')
        elif source_image_url:
            original_image = self.fetch_remote_image(source_image_url)
            if original_image is not None:
                self.show_image(original_image, self.label_out, 'img')

        self.tabel_show_from_detection(detection)

    def show_detection_history(self):
        LIMIT = 20
        current_page = [1]
        total_pages = [1]
        total_count = [0]

        dialog = QDialog(self)
        dialog.setWindowTitle("检测历史记录")
        dialog.resize(960, 520)
        layout = QVBoxLayout(dialog)
        layout.setSpacing(8)

        # ── Filter bar ──────────────────────────────────────────
        filter_row = QHBoxLayout()

        filter_row.addWidget(QLabel("状态:"))
        status_combo = QComboBox()
        status_combo.addItems(["全部", "completed", "failed", "processing", "pending"])
        filter_row.addWidget(status_combo)

        filter_row.addWidget(QLabel("类型:"))
        type_combo = QComboBox()
        type_combo.addItems(["全部", "image", "video"])
        filter_row.addWidget(type_combo)

        refresh_btn = QPushButton("🔍 搜索")
        filter_row.addWidget(refresh_btn)
        filter_row.addStretch()

        summary_label = QLabel("共 0 笔")
        filter_row.addWidget(summary_label)
        layout.addLayout(filter_row)

        # ── Table ────────────────────────────────────────────────
        table = QTableWidget(dialog)
        table.setColumnCount(6)
        table.setHorizontalHeaderLabels(["任务ID", "类型", "文件名", "状态", "目标数", "时间"])
        table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        table.setSelectionBehavior(QTableWidget.SelectRows)
        table.setEditTriggers(QTableWidget.NoEditTriggers)
        layout.addWidget(table)

        # ── Bottom row ───────────────────────────────────────────
        bottom_row = QHBoxLayout()

        prev_btn = QPushButton("← 上一页")
        prev_btn.setEnabled(False)
        bottom_row.addWidget(prev_btn)

        page_label = QLabel("第 1 页 / 共 1 页")
        bottom_row.addWidget(page_label)

        next_btn = QPushButton("下一页 →")
        next_btn.setEnabled(False)
        bottom_row.addWidget(next_btn)

        bottom_row.addStretch()
        delete_btn = QPushButton("🗑 删除选中")
        delete_btn.setEnabled(False)
        bottom_row.addWidget(delete_btn)

        load_btn = QPushButton("📂 载入结果")
        load_btn.setEnabled(False)
        bottom_row.addWidget(load_btn)

        close_button = QPushButton("关闭")
        bottom_row.addWidget(close_button)

        layout.addLayout(bottom_row)

        # ── Helpers ──────────────────────────────────────────────
        def _populate(detections):
            table.setRowCount(len(detections))
            for row, det in enumerate(detections):
                values = [
                    str(det.get("id", "")),
                    str(det.get("source_type", "")),
                    str(det.get("source_filename", "")),
                    str(det.get("status", "")),
                    str(det.get("object_count", 0)),
                    str(det.get("created_at", ""))[:19],
                ]
                for col, val in enumerate(values):
                    cell = QTableWidgetItem(val)
                    cell.setTextAlignment(Qt.AlignHCenter | Qt.AlignVCenter)
                    table.setItem(row, col, cell)
            delete_btn.setEnabled(False)
            load_btn.setEnabled(False)

        def _load(page_num=1):
            raw_status = status_combo.currentText()
            raw_type = type_combo.currentText()
            sel_status = None if raw_status == "全部" else raw_status
            sel_type = None if raw_type == "全部" else raw_type
            try:
                detections, meta = self.api_client.list_detections(
                    self._get_user_access_token(),
                    status=sel_status,
                    source_type=sel_type,
                    limit=LIMIT,
                    page=page_num,
                    with_meta=True,
                )
            except ApiError as exc:
                DialogOver(parent=dialog, text=exc.message, title="读取失败", flags="warning")
                return

            total = meta.get("total", len(detections))
            total_pages = max(1, meta.get("total_pages", 1))
            # 刪掉最後一頁唯一一筆後，退回最後一頁
            if page_num > total_pages:
                _load(total_pages)
                return

            current_page[0] = page_num
            summary_label.setText(f"共 {total} 笔")
            page_label.setText(f"第 {page_num} 页 / 共 {total_pages} 页")
            prev_btn.setEnabled(page_num > 1)
            next_btn.setEnabled(page_num < total_pages)

            _populate(detections)

        def _on_selection_change():
            selected = table.selectedItems()
            delete_btn.setEnabled(bool(selected))
            load_btn.setEnabled(bool(selected))

        def _on_delete():
            rows = table.selectedItems()
            if not rows:
                return
            task_id = int(table.item(table.currentRow(), 0).text())
            filename = table.item(table.currentRow(), 2).text()
            confirm = QDialog(dialog)
            confirm.setWindowTitle("确认删除")
            cl = QVBoxLayout(confirm)
            cl.addWidget(QLabel(f"确定要删除 #{task_id}（{filename}）？"))
            cb = QHBoxLayout()
            yes_btn = QPushButton("删除")
            no_btn = QPushButton("取消")
            cb.addStretch()
            cb.addWidget(yes_btn)
            cb.addWidget(no_btn)
            cl.addLayout(cb)
            yes_btn.clicked.connect(confirm.accept)
            no_btn.clicked.connect(confirm.reject)
            if confirm.exec() != QDialog.Accepted:
                return
            try:
                self.api_client.delete_detection(
                    access_token=self._get_user_access_token(),
                    detection_id=task_id,
                )
            except ApiError as exc:
                DialogOver(parent=dialog, text=exc.message, title="删除失败", flags="warning")
                return
            _load(current_page[0])

        def _on_load():
            self.load_detection_from_history(dialog, table, table.currentRow())

        # ── Wiring ───────────────────────────────────────────────
        refresh_btn.clicked.connect(lambda: _load(1))
        prev_btn.clicked.connect(lambda: _load(current_page[0] - 1))
        next_btn.clicked.connect(lambda: _load(current_page[0] + 1))
        close_button.clicked.connect(dialog.close)
        delete_btn.clicked.connect(_on_delete)
        load_btn.clicked.connect(_on_load)
        table.itemSelectionChanged.connect(_on_selection_change)
        table.itemDoubleClicked.connect(lambda item: _on_load())

        _load(1)
        self.history_dialog = dialog
        dialog.exec()

    def load_detection_from_history(self, dialog, table, row):
        task_id_item = table.item(row, 0)
        if task_id_item is None:
            return

        try:
            detection = self.api_client.get_detection(
                access_token=self._get_user_access_token(),
                detection_id=int(task_id_item.text()),
            )
            self.render_detection_result(detection)
        except ApiError as exc:
            DialogOver(parent=self, text=exc.message, title="读取失败", flags="warning")
            return

        dialog.accept()

    def open_current_result(self):
        if not self.current_detection:
            DialogOver(parent=self, text="目前没有可打开的检测结果", title="打开失败", flags="warning")
            return

        result_path = (
            self.current_detection.get("result_video_url")
            or self.current_detection.get("result_image_url")
            or self.current_detection.get("preview_image_url")
        )
        if not result_path:
            DialogOver(parent=self, text="当前检测结果尚未生成", title="打开失败", flags="warning")
            return

        QDesktopServices.openUrl(QUrl(self.api_client.resolve_url(result_path)))

    def open_agent_window(self, mode: str = "auto", detection_id: int | None = None) -> None:
        """Phase 6A-3 — Open the standalone Agent Console.

        If a detection result is already loaded, pre-fills detection_id and
        defaults to ``explain_detection`` mode so the user can immediately ask
        the Agent to explain the result.
        """
        from AgentWindow import AgentWindow

        effective_detection_id = detection_id
        effective_mode = mode

        if effective_detection_id is None and self.current_detection:
            effective_detection_id = self.current_detection.get("id")
            if effective_detection_id and effective_mode == "auto":
                effective_mode = "explain_detection"

        window = AgentWindow(
            parent=self,
            mode=effective_mode,
            detection_id=effective_detection_id,
        )
        window.exec()

    def fetch_remote_image(self, image_url):
        image_bytes = self.api_client.fetch_binary(image_url)
        return cv2.imdecode(np.frombuffer(image_bytes, dtype=np.uint8), cv2.IMREAD_COLOR)

    def wait_for_detection_completion(self, detection_id, timeout_seconds=1800, poll_interval_seconds=1):
        started_at = time.time()
        while time.time() - started_at < timeout_seconds:
            QApplication.processEvents()
            if self._polling_cancelled:
                raise ApiError("视窗已关闭，检测仍在后台执行，可稍后到历史记录查看结果")
            detection = self.api_client.get_detection(
                access_token=self._get_user_access_token(),
                detection_id=detection_id,
            )
            status = detection.get("status")
            if status == "completed":
                return detection
            if status == "failed":
                raise ApiError(detection.get("error_message") or "检测任务执行失败")
            time.sleep(poll_interval_seconds)

        raise ApiError("检测任务逾时，请稍后到历史记录查看结果")

    def tabel_show_from_detection(self, detection):
        objects = detection.get("objects", [])
        names = {obj["class_id"]: obj["class_name"] for obj in objects}
        ids = [obj.get("object_index", index + 1) for index, obj in enumerate(objects)]
        coordinates = [
            [int(round(value)) for value in obj.get("bbox", [])]
            for obj in objects
        ]
        names_list = [obj.get("class_id", 0) for obj in objects]
        confs = [f'{obj.get("confidence", 0) * 100:.2f} %' for obj in objects]
        path = (
            detection.get("source_image_path")
            or detection.get("source_video_path")
            or detection.get("source_filename")
            or ""
        )
        self.tabel_show(ids, coordinates, names_list, confs, names, path=path)

    def is_image_source(self, source=None):
        source = (source or self.yolo_predict.source or "").lower()
        return source.endswith((".png", ".jpg", ".jpeg", ".bmp", ".webp", ".gif"))

    def is_local_video_source(self, source=None):
        source = (source or self.yolo_predict.source or "").lower()
        if not source or check_url(source):
            return False
        return source.endswith((".mp4", ".avi", ".mkv", ".flv", ".mov"))

    def tabel_show(self, id, coordinates, names_list, confs, names, path=None):
        path = path
        self.tableWidget.setRowCount(0)
        for id, coordinate, cls_name, conf in zip(id, coordinates, names_list, confs):
            row_count = self.tableWidget.rowCount()
            self.tableWidget.insertRow(row_count)

            # 设置每列的内容
            item_id = QTableWidgetItem(str(id))  # 目标id
            item_id.setTextAlignment(Qt.AlignHCenter | Qt.AlignVCenter)
            item_path = QTableWidgetItem(str(path))  # 路径
            item_cls = QTableWidgetItem(str(names[int(cls_name)]))    # 类别名字
            item_cls.setTextAlignment(Qt.AlignHCenter | Qt.AlignVCenter)
            item_conf = QTableWidgetItem(str(conf))  # 置信度
            item_conf.setTextAlignment(Qt.AlignHCenter | Qt.AlignVCenter)
            item_location = QTableWidgetItem(str(coordinate))  # 目标框位置

            # 将数据插入到对应行中
            self.tableWidget.setItem(row_count, 0, item_id)
            self.tableWidget.setItem(row_count, 1, item_path)
            self.tableWidget.setItem(row_count, 2, item_cls)
            self.tableWidget.setItem(row_count, 3, item_conf)
            self.tableWidget.setItem(row_count, 4, item_location)

        # 滚动到表格的底部，显示最新的目标
        self.tableWidget.scrollToBottom()


    def to_close(self):
        self._polling_cancelled = True  # 讓 wait_for_detection_completion 的輪詢跳出
        self.close()

    # 最小化窗口
    def to_minmal(self):
        self.showMinimized()

    # 放大缩小窗口
    def max_or_restore(self):
        if self.max_btn.isChecked():
            self.showMaximized()
        else:
            self.showNormal()

    #鼠标控制 groupBox实现窗口自由移动
    def mousePressEvent(self, event):
        self.m_Position = event.position().toPoint()
        if event.button() == Qt.LeftButton:
            frame_rect = self.frame_6.geometry()  #
            # 检查点击位置是否在 frame_6 内部
            if (frame_rect.left() <= self.m_Position.x() <= frame_rect.right() and
                    frame_rect.top() <= self.m_Position.y() <= frame_rect.bottom()):
                self.m_flag = True

    def mouseMoveEvent(self, event):
        if (event.buttons() & Qt.LeftButton) and self.m_flag:
            self.move(event.globalPosition().toPoint() - self.m_Position)

    def mouseReleaseEvent(self, event):
        self.m_flag = False



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
    app = QApplication(sys.argv)
    Home = Client()
    Home.show()
    sys.exit(app.exec())
