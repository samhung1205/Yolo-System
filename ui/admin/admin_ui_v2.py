# -*- coding: utf-8 -*-

################################################################################
## Form generated from reading UI file 'admin_ui_v2.ui'
##
## Created by: Qt User Interface Compiler version 6.5.1
##
## WARNING! All changes made in this file will be lost when recompiling UI file!
################################################################################

from PySide6.QtCore import (QCoreApplication, QDate, QDateTime, QLocale,
    QMetaObject, QObject, QPoint, QRect,
    QSize, QTime, QUrl, Qt)
from PySide6.QtGui import (QBrush, QColor, QConicalGradient, QCursor,
    QFont, QFontDatabase, QGradient, QIcon,
    QImage, QKeySequence, QLinearGradient, QPainter,
    QPalette, QPixmap, QRadialGradient, QTransform)
from PySide6.QtWidgets import (QAbstractItemView, QApplication, QFrame, QGridLayout,
    QHBoxLayout, QHeaderView, QLabel, QLineEdit,
    QMainWindow, QPushButton, QSizePolicy, QSpacerItem,
    QStackedWidget, QTabWidget, QTableWidget, QTableWidgetItem,
    QVBoxLayout, QWidget)
import admin_icon_rc

class Ui_MainWindow(object):
    def setupUi(self, MainWindow):
        if not MainWindow.objectName():
            MainWindow.setObjectName(u"MainWindow")
        MainWindow.setEnabled(True)
        MainWindow.resize(1000, 630)
        icon = QIcon()
        icon.addFile(u":/img/icons/kk.jpg", QSize(), QIcon.Normal, QIcon.Off)
        MainWindow.setWindowIcon(icon)
        MainWindow.setStyleSheet(u"")
        self.centralwidget = QWidget(MainWindow)
        self.centralwidget.setObjectName(u"centralwidget")
        sizePolicy = QSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        sizePolicy.setHorizontalStretch(0)
        sizePolicy.setVerticalStretch(0)
        sizePolicy.setHeightForWidth(self.centralwidget.sizePolicy().hasHeightForWidth())
        self.centralwidget.setSizePolicy(sizePolicy)
        self.horizontalLayout_4 = QHBoxLayout(self.centralwidget)
        self.horizontalLayout_4.setSpacing(0)
        self.horizontalLayout_4.setObjectName(u"horizontalLayout_4")
        self.horizontalLayout_4.setContentsMargins(0, 0, 0, 0)
        self.frame = QFrame(self.centralwidget)
        self.frame.setObjectName(u"frame")
        sizePolicy1 = QSizePolicy(QSizePolicy.Preferred, QSizePolicy.Preferred)
        sizePolicy1.setHorizontalStretch(0)
        sizePolicy1.setVerticalStretch(0)
        sizePolicy1.setHeightForWidth(self.frame.sizePolicy().hasHeightForWidth())
        self.frame.setSizePolicy(sizePolicy1)
        self.frame.setMinimumSize(QSize(0, 0))
        self.frame.setMaximumSize(QSize(16777215, 16777215))
        self.frame.setStyleSheet(u"QFrame {\n"
"    border: 0px;\n"
"}")
        self.frame.setFrameShape(QFrame.StyledPanel)
        self.frame.setFrameShadow(QFrame.Raised)
        self.horizontalLayout = QHBoxLayout(self.frame)
        self.horizontalLayout.setSpacing(0)
        self.horizontalLayout.setObjectName(u"horizontalLayout")
        self.horizontalLayout.setContentsMargins(0, 0, 0, 0)
        self.frame_7 = QFrame(self.frame)
        self.frame_7.setObjectName(u"frame_7")
        sizePolicy1.setHeightForWidth(self.frame_7.sizePolicy().hasHeightForWidth())
        self.frame_7.setSizePolicy(sizePolicy1)
        self.frame_7.setMinimumSize(QSize(170, 0))
        self.frame_7.setMaximumSize(QSize(16777215, 16777215))
        self.frame_7.setStyleSheet(u"QFrame{\n"
"	\n"
"	background-color: rgb(83, 91, 99);\n"
"\n"
"}")
        self.frame_7.setFrameShape(QFrame.StyledPanel)
        self.frame_7.setFrameShadow(QFrame.Raised)
        self.verticalLayout_3 = QVBoxLayout(self.frame_7)
        self.verticalLayout_3.setSpacing(0)
        self.verticalLayout_3.setObjectName(u"verticalLayout_3")
        self.verticalLayout_3.setContentsMargins(0, 0, 0, 0)
        self.frame_8 = QFrame(self.frame_7)
        self.frame_8.setObjectName(u"frame_8")
        sizePolicy2 = QSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        sizePolicy2.setHorizontalStretch(4)
        sizePolicy2.setVerticalStretch(0)
        sizePolicy2.setHeightForWidth(self.frame_8.sizePolicy().hasHeightForWidth())
        self.frame_8.setSizePolicy(sizePolicy2)
        self.frame_8.setMaximumSize(QSize(16777215, 9))
        self.frame_8.setFrameShape(QFrame.StyledPanel)
        self.frame_8.setFrameShadow(QFrame.Raised)
        self.horizontalLayout_5 = QHBoxLayout(self.frame_8)
        self.horizontalLayout_5.setObjectName(u"horizontalLayout_5")

        self.verticalLayout_3.addWidget(self.frame_8)

        self.frame_3 = QFrame(self.frame_7)
        self.frame_3.setObjectName(u"frame_3")
        sizePolicy2.setHeightForWidth(self.frame_3.sizePolicy().hasHeightForWidth())
        self.frame_3.setSizePolicy(sizePolicy2)
        self.frame_3.setMaximumSize(QSize(16777215, 16777215))
        self.frame_3.setStyleSheet(u"\n"
"QPushButton{\n"
"	border:none;\n"
"	color: rgb(255, 255, 255);\n"
"    font:  14px \"\u5fae\u8f6f\u96c5\u9ed1\";  \n"
"\n"
"}\n"
"QPushButton:hover { \n"
"	background-color: #49494e;\n"
"	color: rgb(96, 152, 234);\n"
"\n"
" }\n"
"\n"
"")
        self.frame_3.setFrameShape(QFrame.StyledPanel)
        self.frame_3.setFrameShadow(QFrame.Raised)
        self.frame_3.setLineWidth(1)
        self.verticalLayout = QVBoxLayout(self.frame_3)
        self.verticalLayout.setSpacing(0)
        self.verticalLayout.setObjectName(u"verticalLayout")
        self.verticalLayout.setContentsMargins(0, 0, 0, 0)
        self.index_btn = QPushButton(self.frame_3)
        self.index_btn.setObjectName(u"index_btn")
        sizePolicy3 = QSizePolicy(QSizePolicy.Minimum, QSizePolicy.Expanding)
        sizePolicy3.setHorizontalStretch(0)
        sizePolicy3.setVerticalStretch(0)
        sizePolicy3.setHeightForWidth(self.index_btn.sizePolicy().hasHeightForWidth())
        self.index_btn.setSizePolicy(sizePolicy3)
        self.index_btn.setMinimumSize(QSize(0, 35))
        font = QFont()
        font.setFamilies([u"\u5fae\u8f6f\u96c5\u9ed1"])
        font.setBold(False)
        font.setItalic(False)
        self.index_btn.setFont(font)
        self.index_btn.setStyleSheet(u"")
        icon1 = QIcon()
        icon1.addFile(u":/img/img/\u9996\u9875.png", QSize(), QIcon.Normal, QIcon.Off)
        self.index_btn.setIcon(icon1)
        self.index_btn.setIconSize(QSize(16, 16))

        self.verticalLayout.addWidget(self.index_btn)

        self.verticalSpacer = QSpacerItem(20, 15, QSizePolicy.Minimum, QSizePolicy.Expanding)

        self.verticalLayout.addItem(self.verticalSpacer)

        self.user_manage_btn = QPushButton(self.frame_3)
        self.user_manage_btn.setObjectName(u"user_manage_btn")
        sizePolicy3.setHeightForWidth(self.user_manage_btn.sizePolicy().hasHeightForWidth())
        self.user_manage_btn.setSizePolicy(sizePolicy3)
        self.user_manage_btn.setMinimumSize(QSize(0, 35))
        icon2 = QIcon()
        icon2.addFile(u":/img/img/\u7528\u6237\u8bbe\u7f6e.png", QSize(), QIcon.Normal, QIcon.Off)
        self.user_manage_btn.setIcon(icon2)
        self.user_manage_btn.setIconSize(QSize(19, 17))

        self.verticalLayout.addWidget(self.user_manage_btn)

        self.verticalSpacer_2 = QSpacerItem(20, 15, QSizePolicy.Minimum, QSizePolicy.Expanding)

        self.verticalLayout.addItem(self.verticalSpacer_2)

        self.admin_info_btn = QPushButton(self.frame_3)
        self.admin_info_btn.setObjectName(u"admin_info_btn")
        sizePolicy3.setHeightForWidth(self.admin_info_btn.sizePolicy().hasHeightForWidth())
        self.admin_info_btn.setSizePolicy(sizePolicy3)
        self.admin_info_btn.setMinimumSize(QSize(0, 35))
        self.admin_info_btn.setAutoFillBackground(False)
        icon3 = QIcon()
        icon3.addFile(u":/img/img/\u4e2a\u4eba\u4e2d\u5fc3.png", QSize(), QIcon.Normal, QIcon.Off)
        self.admin_info_btn.setIcon(icon3)
        self.admin_info_btn.setIconSize(QSize(16, 16))

        self.verticalLayout.addWidget(self.admin_info_btn)

        self.verticalSpacer_3 = QSpacerItem(20, 15, QSizePolicy.Minimum, QSizePolicy.Expanding)

        self.verticalLayout.addItem(self.verticalSpacer_3)

        self.exit_btn = QPushButton(self.frame_3)
        self.exit_btn.setObjectName(u"exit_btn")
        sizePolicy3.setHeightForWidth(self.exit_btn.sizePolicy().hasHeightForWidth())
        self.exit_btn.setSizePolicy(sizePolicy3)
        self.exit_btn.setMinimumSize(QSize(0, 35))
        self.exit_btn.setLayoutDirection(Qt.LeftToRight)
        self.exit_btn.setStyleSheet(u"")
        icon4 = QIcon()
        icon4.addFile(u":/img/img/\u9000\u51fa.png", QSize(), QIcon.Normal, QIcon.Off)
        self.exit_btn.setIcon(icon4)
        self.exit_btn.setIconSize(QSize(14, 14))
        self.exit_btn.setAutoRepeatDelay(300)

        self.verticalLayout.addWidget(self.exit_btn)

        self.verticalSpacer_4 = QSpacerItem(20, 40, QSizePolicy.Minimum, QSizePolicy.Expanding)

        self.verticalLayout.addItem(self.verticalSpacer_4)


        self.verticalLayout_3.addWidget(self.frame_3)

        self.frame_9 = QFrame(self.frame_7)
        self.frame_9.setObjectName(u"frame_9")
        sizePolicy4 = QSizePolicy(QSizePolicy.Preferred, QSizePolicy.Expanding)
        sizePolicy4.setHorizontalStretch(0)
        sizePolicy4.setVerticalStretch(3)
        sizePolicy4.setHeightForWidth(self.frame_9.sizePolicy().hasHeightForWidth())
        self.frame_9.setSizePolicy(sizePolicy4)
        self.frame_9.setFrameShape(QFrame.StyledPanel)
        self.frame_9.setFrameShadow(QFrame.Raised)

        self.verticalLayout_3.addWidget(self.frame_9)


        self.horizontalLayout.addWidget(self.frame_7)

        self.verticalLayout_2 = QVBoxLayout()
        self.verticalLayout_2.setSpacing(0)
        self.verticalLayout_2.setObjectName(u"verticalLayout_2")
        self.verticalLayout_2.setContentsMargins(0, -1, 0, -1)
        self.frame_5 = QFrame(self.frame)
        self.frame_5.setObjectName(u"frame_5")
        sizePolicy5 = QSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        sizePolicy5.setHorizontalStretch(10)
        sizePolicy5.setVerticalStretch(1)
        sizePolicy5.setHeightForWidth(self.frame_5.sizePolicy().hasHeightForWidth())
        self.frame_5.setSizePolicy(sizePolicy5)
        self.frame_5.setStyleSheet(u"QFrame#frame_5 {\n"
"    border: 1px solid  rgb(190, 190, 190) ;\n"
"}")
        self.frame_5.setFrameShape(QFrame.StyledPanel)
        self.frame_5.setFrameShadow(QFrame.Raised)
        self.frame_5.setLineWidth(1)
        self.horizontalLayout_6 = QHBoxLayout(self.frame_5)
        self.horizontalLayout_6.setSpacing(0)
        self.horizontalLayout_6.setObjectName(u"horizontalLayout_6")
        self.horizontalLayout_6.setContentsMargins(0, 0, 0, 0)
        self.frame_6 = QFrame(self.frame_5)
        self.frame_6.setObjectName(u"frame_6")
        self.frame_6.setStyleSheet(u"background-color: rgb(255, 255, 255);\n"
"")
        self.frame_6.setFrameShape(QFrame.StyledPanel)
        self.frame_6.setFrameShadow(QFrame.Raised)
        self.horizontalLayout_3 = QHBoxLayout(self.frame_6)
        self.horizontalLayout_3.setSpacing(0)
        self.horizontalLayout_3.setObjectName(u"horizontalLayout_3")
        self.horizontalLayout_3.setContentsMargins(0, 0, 12, 0)
        self.horizontalSpacer_2 = QSpacerItem(619, 20, QSizePolicy.Expanding, QSizePolicy.Minimum)

        self.horizontalLayout_3.addItem(self.horizontalSpacer_2)

        self.label = QLabel(self.frame_6)
        self.label.setObjectName(u"label")
        font1 = QFont()
        font1.setFamilies([u"\u534e\u6587\u7ec6\u9ed1"])
        font1.setBold(True)
        font1.setItalic(False)
        self.label.setFont(font1)
        self.label.setStyleSheet(u"\n"
"font-size: 19px;")

        self.horizontalLayout_3.addWidget(self.label)

        self.horizontalSpacer = QSpacerItem(619, 20, QSizePolicy.Expanding, QSizePolicy.Minimum)

        self.horizontalLayout_3.addItem(self.horizontalSpacer)

        self.horizontalLayout_2 = QHBoxLayout()
        self.horizontalLayout_2.setSpacing(0)
        self.horizontalLayout_2.setObjectName(u"horizontalLayout_2")
        self.horizontalLayout_2.setContentsMargins(11, -1, 4, -1)
        self.label_userAvatar = QLabel(self.frame_6)
        self.label_userAvatar.setObjectName(u"label_userAvatar")
        self.label_userAvatar.setEnabled(True)
        self.label_userAvatar.setMaximumSize(QSize(35, 35))
        self.label_userAvatar.setStyleSheet(u"")
        self.label_userAvatar.setPixmap(QPixmap(u":/img/img/kk.jpg"))
        self.label_userAvatar.setScaledContents(True)
        self.label_userAvatar.setAlignment(Qt.AlignCenter)

        self.horizontalLayout_2.addWidget(self.label_userAvatar)

        self.pushButton_mian_username = QPushButton(self.frame_6)
        self.pushButton_mian_username.setObjectName(u"pushButton_mian_username")
        self.pushButton_mian_username.setMinimumSize(QSize(48, 23))
        self.pushButton_mian_username.setMaximumSize(QSize(160, 23))
        self.pushButton_mian_username.setLayoutDirection(Qt.RightToLeft)
        self.pushButton_mian_username.setAutoFillBackground(False)
        self.pushButton_mian_username.setStyleSheet(u"QPushButton{\n"
"	\n"
"	border: 0px;\n"
"    font:12px;\n"
"\n"
"}\n"
"\n"
"\n"
"\n"
"")
        self.pushButton_mian_username.setIconSize(QSize(12, 12))
        self.pushButton_mian_username.setFlat(False)

        self.horizontalLayout_2.addWidget(self.pushButton_mian_username)


        self.horizontalLayout_3.addLayout(self.horizontalLayout_2)


        self.horizontalLayout_6.addWidget(self.frame_6)


        self.verticalLayout_2.addWidget(self.frame_5)

        self.frame_2 = QFrame(self.frame)
        self.frame_2.setObjectName(u"frame_2")
        sizePolicy6 = QSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        sizePolicy6.setHorizontalStretch(10)
        sizePolicy6.setVerticalStretch(14)
        sizePolicy6.setHeightForWidth(self.frame_2.sizePolicy().hasHeightForWidth())
        self.frame_2.setSizePolicy(sizePolicy6)
        self.frame_2.setStyleSheet(u"background-color: rgb(255, 255, 255);")
        self.frame_2.setFrameShape(QFrame.StyledPanel)
        self.frame_2.setFrameShadow(QFrame.Raised)
        self.frame_2.setLineWidth(1)
        self.frame_4 = QFrame(self.frame_2)
        self.frame_4.setObjectName(u"frame_4")
        self.frame_4.setGeometry(QRect(0, 0, 821, 581))
        sizePolicy7 = QSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        sizePolicy7.setHorizontalStretch(4)
        sizePolicy7.setVerticalStretch(0)
        sizePolicy7.setHeightForWidth(self.frame_4.sizePolicy().hasHeightForWidth())
        self.frame_4.setSizePolicy(sizePolicy7)
        self.frame_4.setStyleSheet(u"")
        self.frame_4.setFrameShape(QFrame.StyledPanel)
        self.frame_4.setFrameShadow(QFrame.Raised)
        self.frame_4.setLineWidth(1)
        self.horizontalLayout_7 = QHBoxLayout(self.frame_4)
        self.horizontalLayout_7.setSpacing(0)
        self.horizontalLayout_7.setObjectName(u"horizontalLayout_7")
        self.horizontalLayout_7.setContentsMargins(0, 0, 0, 0)
        self.stackedWidget = QStackedWidget(self.frame_4)
        self.stackedWidget.setObjectName(u"stackedWidget")
        self.page = QWidget()
        self.page.setObjectName(u"page")
        self.layoutWidget = QWidget(self.page)
        self.layoutWidget.setObjectName(u"layoutWidget")
        self.layoutWidget.setGeometry(QRect(130, 210, 583, 123))
        self.gridLayout_3 = QGridLayout(self.layoutWidget)
        self.gridLayout_3.setObjectName(u"gridLayout_3")
        self.gridLayout_3.setContentsMargins(0, 0, 0, 0)
        self.verticalSpacer_5 = QSpacerItem(20, 40, QSizePolicy.Minimum, QSizePolicy.Expanding)

        self.gridLayout_3.addItem(self.verticalSpacer_5, 0, 0, 1, 1)

        self.horizontalLayout_13 = QHBoxLayout()
        self.horizontalLayout_13.setObjectName(u"horizontalLayout_13")
        self.horizontalSpacer_5 = QSpacerItem(40, 20, QSizePolicy.Expanding, QSizePolicy.Minimum)

        self.horizontalLayout_13.addItem(self.horizontalSpacer_5)

        self.label_2 = QLabel(self.layoutWidget)
        self.label_2.setObjectName(u"label_2")
        font2 = QFont()
        font2.setPointSize(20)
        self.label_2.setFont(font2)
        self.label_2.setAlignment(Qt.AlignCenter)

        self.horizontalLayout_13.addWidget(self.label_2)

        self.horizontalSpacer_6 = QSpacerItem(40, 20, QSizePolicy.Expanding, QSizePolicy.Minimum)

        self.horizontalLayout_13.addItem(self.horizontalSpacer_6)


        self.gridLayout_3.addLayout(self.horizontalLayout_13, 1, 0, 1, 1)

        self.verticalSpacer_6 = QSpacerItem(20, 40, QSizePolicy.Minimum, QSizePolicy.Expanding)

        self.gridLayout_3.addItem(self.verticalSpacer_6, 2, 0, 1, 1)

        self.stackedWidget.addWidget(self.page)
        self.page_2 = QWidget()
        self.page_2.setObjectName(u"page_2")
        self.gridLayout = QGridLayout(self.page_2)
        self.gridLayout.setSpacing(0)
        self.gridLayout.setObjectName(u"gridLayout")
        self.gridLayout.setContentsMargins(0, 0, 0, 0)
        self.frame_10 = QFrame(self.page_2)
        self.frame_10.setObjectName(u"frame_10")
        self.frame_10.setStyleSheet(u"")
        self.frame_10.setFrameShape(QFrame.StyledPanel)
        self.frame_10.setFrameShadow(QFrame.Raised)
        self.verticalLayout_4 = QVBoxLayout(self.frame_10)
        self.verticalLayout_4.setSpacing(0)
        self.verticalLayout_4.setObjectName(u"verticalLayout_4")
        self.verticalLayout_4.setContentsMargins(0, 0, 0, 0)
        self.frame_12 = QFrame(self.frame_10)
        self.frame_12.setObjectName(u"frame_12")
        sizePolicy8 = QSizePolicy(QSizePolicy.Preferred, QSizePolicy.Expanding)
        sizePolicy8.setHorizontalStretch(0)
        sizePolicy8.setVerticalStretch(1)
        sizePolicy8.setHeightForWidth(self.frame_12.sizePolicy().hasHeightForWidth())
        self.frame_12.setSizePolicy(sizePolicy8)
        self.frame_12.setMaximumSize(QSize(16777215, 19))
        self.frame_12.setFrameShape(QFrame.StyledPanel)
        self.frame_12.setFrameShadow(QFrame.Raised)
        self.horizontalLayout_10 = QHBoxLayout(self.frame_12)
        self.horizontalLayout_10.setObjectName(u"horizontalLayout_10")

        self.verticalLayout_4.addWidget(self.frame_12)

        self.frame_13 = QFrame(self.frame_10)
        self.frame_13.setObjectName(u"frame_13")
        sizePolicy8.setHeightForWidth(self.frame_13.sizePolicy().hasHeightForWidth())
        self.frame_13.setSizePolicy(sizePolicy8)
        self.frame_13.setMaximumSize(QSize(16777215, 63))
        font3 = QFont()
        font3.setBold(False)
        self.frame_13.setFont(font3)
        self.frame_13.setStyleSheet(u"QPushButton{\n"
"	background-color: rgb(52, 148, 254);\n"
"    font: 16px \"Arial\";\n"
"	color: rgb(255, 255, 255);\n"
"    border:none;\n"
"    border-radius:10px;\n"
"    width:150px;\n"
"    height:30px;\n"
"    padding-left:5px;\n"
"    padding-right:5px;\n"
"}\n"
"QPushButton:hover{\n"
"	background-color: rgb(86, 164, 251);\n"
"}")
        self.frame_13.setFrameShape(QFrame.StyledPanel)
        self.frame_13.setFrameShadow(QFrame.Raised)
        self.horizontalLayout_9 = QHBoxLayout(self.frame_13)
        self.horizontalLayout_9.setSpacing(0)
        self.horizontalLayout_9.setObjectName(u"horizontalLayout_9")
        self.horizontalLayout_9.setContentsMargins(9, 0, 9, 6)
        self.horizontalSpacer_10 = QSpacerItem(40, 20, QSizePolicy.Expanding, QSizePolicy.Minimum)

        self.horizontalLayout_9.addItem(self.horizontalSpacer_10)

        self.account_lineEdit = QLineEdit(self.frame_13)
        self.account_lineEdit.setObjectName(u"account_lineEdit")
        self.account_lineEdit.setMinimumSize(QSize(140, 0))
        self.account_lineEdit.setStyleSheet(u"border-radius:10px;\n"
"height:24px;\n"
"border:1px solid black;")

        self.horizontalLayout_9.addWidget(self.account_lineEdit)

        self.horizontalSpacer_9 = QSpacerItem(40, 20, QSizePolicy.Expanding, QSizePolicy.Minimum)

        self.horizontalLayout_9.addItem(self.horizontalSpacer_9)

        self.nikename_lineEdit = QLineEdit(self.frame_13)
        self.nikename_lineEdit.setObjectName(u"nikename_lineEdit")
        self.nikename_lineEdit.setMinimumSize(QSize(140, 0))
        self.nikename_lineEdit.setStyleSheet(u"border-radius:10px;\n"
"height:24px;\n"
"border:1px solid black;")

        self.horizontalLayout_9.addWidget(self.nikename_lineEdit)

        self.horizontalSpacer_11 = QSpacerItem(40, 20, QSizePolicy.Expanding, QSizePolicy.Minimum)

        self.horizontalLayout_9.addItem(self.horizontalSpacer_11)

        self.select_pushButton = QPushButton(self.frame_13)
        self.select_pushButton.setObjectName(u"select_pushButton")
        self.select_pushButton.setMinimumSize(QSize(30, 0))
        self.select_pushButton.setMaximumSize(QSize(100, 16777215))
        font4 = QFont()
        font4.setFamilies([u"Arial"])
        font4.setBold(False)
        font4.setItalic(False)
        self.select_pushButton.setFont(font4)
        self.select_pushButton.setStyleSheet(u"")
        icon5 = QIcon()
        icon5.addFile(u":/img/img/\u641c\u7d22.png", QSize(), QIcon.Normal, QIcon.Off)
        self.select_pushButton.setIcon(icon5)

        self.horizontalLayout_9.addWidget(self.select_pushButton)

        self.horizontalSpacer_3 = QSpacerItem(40, 20, QSizePolicy.Expanding, QSizePolicy.Minimum)

        self.horizontalLayout_9.addItem(self.horizontalSpacer_3)

        self.add_pushButton = QPushButton(self.frame_13)
        self.add_pushButton.setObjectName(u"add_pushButton")
        self.add_pushButton.setMaximumSize(QSize(100, 16777215))
        self.add_pushButton.setStyleSheet(u"")
        icon6 = QIcon()
        icon6.addFile(u":/img/img/\u65b0\u589e.png", QSize(), QIcon.Normal, QIcon.Off)
        self.add_pushButton.setIcon(icon6)

        self.horizontalLayout_9.addWidget(self.add_pushButton)

        self.horizontalSpacer_8 = QSpacerItem(40, 20, QSizePolicy.Expanding, QSizePolicy.Minimum)

        self.horizontalLayout_9.addItem(self.horizontalSpacer_8)

        self.delete_pushButton = QPushButton(self.frame_13)
        self.delete_pushButton.setObjectName(u"delete_pushButton")
        self.delete_pushButton.setMaximumSize(QSize(100, 16777215))
        icon7 = QIcon()
        icon7.addFile(u":/img/img/\u5220\u9664.png", QSize(), QIcon.Normal, QIcon.Off)
        self.delete_pushButton.setIcon(icon7)

        self.horizontalLayout_9.addWidget(self.delete_pushButton)

        self.horizontalSpacer_4 = QSpacerItem(40, 20, QSizePolicy.Expanding, QSizePolicy.Minimum)

        self.horizontalLayout_9.addItem(self.horizontalSpacer_4)


        self.verticalLayout_4.addWidget(self.frame_13)

        self.frame_14 = QFrame(self.frame_10)
        self.frame_14.setObjectName(u"frame_14")
        sizePolicy9 = QSizePolicy(QSizePolicy.Preferred, QSizePolicy.Expanding)
        sizePolicy9.setHorizontalStretch(0)
        sizePolicy9.setVerticalStretch(10)
        sizePolicy9.setHeightForWidth(self.frame_14.sizePolicy().hasHeightForWidth())
        self.frame_14.setSizePolicy(sizePolicy9)
        self.frame_14.setMaximumSize(QSize(16777215, 16777215))
        self.frame_14.setStyleSheet(u"QTableWidget {\n"
"                background-color: #ffffff;\n"
"                border-radius: 15px;\n"
"                border: 1px solid #ddd;\n"
"                padding: 5px;\n"
"                box-shadow: 0 4px 8px rgba(0, 0, 0, 0.1);\n"
"            }\n"
"            QHeaderView::section {\n"
"            background-color: rgb(235, 237, 246);  /* \u8868\u5934\u80cc\u666f */\n"
"            border: none;  /* \u65e0\u8fb9\u6846 */\n"
"            padding: 8px;\n"
"        }\n"
"                QTableWidget::item {\n"
"                border-left: 1px solid #ddd;  /* \u8bbe\u7f6e\u6bcf\u4e2a\u5355\u5143\u683c\u5de6\u8fb9\u6846 */\n"
"            }")
        self.frame_14.setFrameShape(QFrame.StyledPanel)
        self.frame_14.setFrameShadow(QFrame.Raised)
        self.horizontalLayout_8 = QHBoxLayout(self.frame_14)
        self.horizontalLayout_8.setSpacing(0)
        self.horizontalLayout_8.setObjectName(u"horizontalLayout_8")
        self.horizontalLayout_8.setContentsMargins(9, 0, 9, 0)
        self.user_tableWidget = QTableWidget(self.frame_14)
        if (self.user_tableWidget.columnCount() < 6):
            self.user_tableWidget.setColumnCount(6)
        __qtablewidgetitem = QTableWidgetItem()
        self.user_tableWidget.setHorizontalHeaderItem(0, __qtablewidgetitem)
        __qtablewidgetitem1 = QTableWidgetItem()
        self.user_tableWidget.setHorizontalHeaderItem(1, __qtablewidgetitem1)
        __qtablewidgetitem2 = QTableWidgetItem()
        self.user_tableWidget.setHorizontalHeaderItem(2, __qtablewidgetitem2)
        __qtablewidgetitem3 = QTableWidgetItem()
        self.user_tableWidget.setHorizontalHeaderItem(3, __qtablewidgetitem3)
        __qtablewidgetitem4 = QTableWidgetItem()
        self.user_tableWidget.setHorizontalHeaderItem(4, __qtablewidgetitem4)
        __qtablewidgetitem5 = QTableWidgetItem()
        self.user_tableWidget.setHorizontalHeaderItem(5, __qtablewidgetitem5)
        self.user_tableWidget.setObjectName(u"user_tableWidget")
        self.user_tableWidget.setFont(font4)
        self.user_tableWidget.setFocusPolicy(Qt.NoFocus)
        self.user_tableWidget.setStyleSheet(u"font: 16px \"Arial\";\n"
"QTableWidget {\n"
"                background-color: #ffffff;\n"
"                border-radius: 15px;\n"
"                border: 1px solid #ddd;\n"
"                padding: 5px;\n"
"                box-shadow: 0 4px 8px rgba(0, 0, 0, 0.1);\n"
"            }\n"
"            QHeaderView::section {\n"
"            background-color: rgb(235, 237, 246);  /* \u8868\u5934\u80cc\u666f */\n"
"            border: none;  /* \u65e0\u8fb9\u6846 */\n"
"            padding: 8px;\n"
"        }\n"
"                QTableWidget::item {\n"
"                border-left: 1px solid #ddd;  /* \u8bbe\u7f6e\u6bcf\u4e2a\u5355\u5143\u683c\u5de6\u8fb9\u6846 */\n"
"            }\n"
"\n"
"")
        self.user_tableWidget.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.user_tableWidget.setSelectionBehavior(QAbstractItemView.SelectItems)
        self.user_tableWidget.horizontalHeader().setCascadingSectionResizes(False)
        self.user_tableWidget.horizontalHeader().setProperty("showSortIndicator", False)
        self.user_tableWidget.horizontalHeader().setStretchLastSection(False)
        self.user_tableWidget.verticalHeader().setVisible(False)
        self.user_tableWidget.verticalHeader().setCascadingSectionResizes(False)
        self.user_tableWidget.verticalHeader().setStretchLastSection(False)

        self.horizontalLayout_8.addWidget(self.user_tableWidget)


        self.verticalLayout_4.addWidget(self.frame_14)


        self.gridLayout.addWidget(self.frame_10, 0, 0, 1, 1)

        self.stackedWidget.addWidget(self.page_2)
        self.page_3 = QWidget()
        self.page_3.setObjectName(u"page_3")
        self.frame_15 = QFrame(self.page_3)
        self.frame_15.setObjectName(u"frame_15")
        self.frame_15.setGeometry(QRect(0, 0, 801, 591))
        self.frame_15.setStyleSheet(u"")
        self.frame_15.setFrameShape(QFrame.StyledPanel)
        self.frame_15.setFrameShadow(QFrame.Raised)
        self.frame_17 = QFrame(self.frame_15)
        self.frame_17.setObjectName(u"frame_17")
        self.frame_17.setGeometry(QRect(0, 0, 801, 591))
        self.frame_17.setStyleSheet(u"QLineEdit{\n"
"border-radius:5px;\n"
"background:#FFFFFF;\n"
"border:1px solid;\n"
"border-color: rgb(104, 164, 253);\n"
"font:  13px;  \n"
"}\n"
"QPushButton{\n"
"    background-color: rgb(104, 164, 253);\n"
"     \n"
"    font: 18px \"Arial Black\";\n"
"    border-radius:10px;\n"
"    \n"
"}\n"
"QPushButton:hover { \n"
"   \n"
"	background-color: rgb(89, 142, 217);  \n"
" }\n"
"\n"
"")
        self.frame_17.setFrameShape(QFrame.StyledPanel)
        self.frame_17.setFrameShadow(QFrame.Raised)
        self.tabWidget = QTabWidget(self.frame_17)
        self.tabWidget.setObjectName(u"tabWidget")
        self.tabWidget.setGeometry(QRect(0, -1, 801, 571))
        self.tabWidget.setStyleSheet(u"QTabWidget:pane\n"
"{\n"
"	top:10px;\n"
"    border: none;  \n"
"}\n"
"\n"
"QTabBar:tab\n"
"{ \n"
"	background:transparent;\n"
"	border-bottom: 2px solid rgb(240, 240, 240);\n"
"	font-family:\"\u5fae\u8f6f\u96c5\u9ed1\";\n"
"	font-size:14px;\n"
"	padding-left:5px;\n"
"	padding-right:5px;\n"
"	min-width: 85px;\n"
"	min-height:30px;		\n"
"}\n"
" \n"
"QTabBar:tab:selected\n"
"{\n"
"	border-bottom: 2px solid rgb(166, 216, 125);\n"
"	color: rgb(166, 216, 125);\n"
"	font-size:15px;\n"
"	font-weight: bold;\n"
"}\n"
"\n"
"QTabBar:tab:hover\n"
"{\n"
"   \n"
"	color: rgb(166, 216, 125);\n"
"\n"
"}")
        self.tab_mainui_PersonalInfo = QWidget()
        self.tab_mainui_PersonalInfo.setObjectName(u"tab_mainui_PersonalInfo")
        self.handleClose_btn = QPushButton(self.tab_mainui_PersonalInfo)
        self.handleClose_btn.setObjectName(u"handleClose_btn")
        self.handleClose_btn.setGeometry(QRect(320, 440, 81, 31))
        self.handleClose_btn.setStyleSheet(u"")
        self.label_avatar = QLabel(self.tab_mainui_PersonalInfo)
        self.label_avatar.setObjectName(u"label_avatar")
        self.label_avatar.setGeometry(QRect(340, 40, 140, 140))
        self.label_avatar.setStyleSheet(u"")
        self.label_avatar.setPixmap(QPixmap(u":/img/img/kk.jpg"))
        self.label_avatar.setScaledContents(True)
        self.label_avatar.setAlignment(Qt.AlignCenter)
        self.label_25 = QLabel(self.tab_mainui_PersonalInfo)
        self.label_25.setObjectName(u"label_25")
        self.label_25.setGeometry(QRect(190, 220, 111, 51))
        self.label_25.setStyleSheet(u"font:  13px; ")
        self.label_25.setAlignment(Qt.AlignCenter)
        self.label_24 = QLabel(self.tab_mainui_PersonalInfo)
        self.label_24.setObjectName(u"label_24")
        self.label_24.setGeometry(QRect(190, 360, 111, 51))
        self.label_24.setStyleSheet(u"font:  13px; ")
        self.label_24.setAlignment(Qt.AlignCenter)
        self.lineEdit_createTime = QLineEdit(self.tab_mainui_PersonalInfo)
        self.lineEdit_createTime.setObjectName(u"lineEdit_createTime")
        self.lineEdit_createTime.setGeometry(QRect(300, 370, 221, 31))
        self.handleSubmit_btn = QPushButton(self.tab_mainui_PersonalInfo)
        self.handleSubmit_btn.setObjectName(u"handleSubmit_btn")
        self.handleSubmit_btn.setGeometry(QRect(420, 440, 81, 31))
        self.handleSubmit_btn.setStyleSheet(u"")
        self.lineEdit_phone = QLineEdit(self.tab_mainui_PersonalInfo)
        self.lineEdit_phone.setObjectName(u"lineEdit_phone")
        self.lineEdit_phone.setGeometry(QRect(300, 300, 221, 31))
        self.lineEdit_phone.setStyleSheet(u"")
        self.lineEdit_name = QLineEdit(self.tab_mainui_PersonalInfo)
        self.lineEdit_name.setObjectName(u"lineEdit_name")
        self.lineEdit_name.setGeometry(QRect(300, 230, 221, 31))
        self.lineEdit_name.setDragEnabled(False)
        self.lineEdit_name.setReadOnly(False)
        self.lineEdit_name.setClearButtonEnabled(False)
        self.label_26 = QLabel(self.tab_mainui_PersonalInfo)
        self.label_26.setObjectName(u"label_26")
        self.label_26.setGeometry(QRect(190, 290, 101, 51))
        self.label_26.setStyleSheet(u"font:  13px; ")
        self.label_26.setAlignment(Qt.AlignCenter)
        self.tabWidget.addTab(self.tab_mainui_PersonalInfo, "")
        self.tab_mainui_SecurityCenter = QWidget()
        self.tab_mainui_SecurityCenter.setObjectName(u"tab_mainui_SecurityCenter")
        self.label_27 = QLabel(self.tab_mainui_SecurityCenter)
        self.label_27.setObjectName(u"label_27")
        self.label_27.setGeometry(QRect(210, 160, 111, 51))
        self.label_27.setStyleSheet(u"font:  13px; ")
        self.label_27.setAlignment(Qt.AlignCenter)
        self.label_28 = QLabel(self.tab_mainui_SecurityCenter)
        self.label_28.setObjectName(u"label_28")
        self.label_28.setGeometry(QRect(210, 300, 111, 51))
        self.label_28.setStyleSheet(u"font:  13px; ")
        self.label_28.setAlignment(Qt.AlignCenter)
        self.lineEdit_check_password = QLineEdit(self.tab_mainui_SecurityCenter)
        self.lineEdit_check_password.setObjectName(u"lineEdit_check_password")
        self.lineEdit_check_password.setGeometry(QRect(320, 310, 221, 31))
        self.lineEdit_check_password.setEchoMode(QLineEdit.Password)
        self.lineEdit_check_password.setClearButtonEnabled(True)
        self.handleSubmit_btn_password = QPushButton(self.tab_mainui_SecurityCenter)
        self.handleSubmit_btn_password.setObjectName(u"handleSubmit_btn_password")
        self.handleSubmit_btn_password.setGeometry(QRect(320, 380, 221, 31))
        self.handleSubmit_btn_password.setStyleSheet(u"")
        self.lineEdit_new_password = QLineEdit(self.tab_mainui_SecurityCenter)
        self.lineEdit_new_password.setObjectName(u"lineEdit_new_password")
        self.lineEdit_new_password.setGeometry(QRect(320, 240, 221, 31))
        self.lineEdit_new_password.setStyleSheet(u"")
        self.lineEdit_new_password.setEchoMode(QLineEdit.Password)
        self.lineEdit_new_password.setClearButtonEnabled(True)
        self.lineEdit_old_password = QLineEdit(self.tab_mainui_SecurityCenter)
        self.lineEdit_old_password.setObjectName(u"lineEdit_old_password")
        self.lineEdit_old_password.setGeometry(QRect(320, 170, 221, 31))
        self.lineEdit_old_password.setEchoMode(QLineEdit.Password)
        self.lineEdit_old_password.setDragEnabled(False)
        self.lineEdit_old_password.setReadOnly(False)
        self.lineEdit_old_password.setClearButtonEnabled(True)
        self.label_34 = QLabel(self.tab_mainui_SecurityCenter)
        self.label_34.setObjectName(u"label_34")
        self.label_34.setGeometry(QRect(210, 230, 110, 51))
        self.label_34.setStyleSheet(u"font:  13px; ")
        self.label_34.setAlignment(Qt.AlignCenter)
        self.label_3 = QLabel(self.tab_mainui_SecurityCenter)
        self.label_3.setObjectName(u"label_3")
        self.label_3.setGeometry(QRect(390, 90, 81, 42))
        font5 = QFont()
        font5.setFamilies([u"\u534e\u6587\u5f69\u4e91"])
        font5.setBold(True)
        font5.setItalic(False)
        self.label_3.setFont(font5)
        self.label_3.setStyleSheet(u"font-size: 19px;")
        self.tabWidget.addTab(self.tab_mainui_SecurityCenter, "")
        self.stackedWidget.addWidget(self.page_3)

        self.horizontalLayout_7.addWidget(self.stackedWidget)


        self.verticalLayout_2.addWidget(self.frame_2)


        self.horizontalLayout.addLayout(self.verticalLayout_2)


        self.horizontalLayout_4.addWidget(self.frame)

        MainWindow.setCentralWidget(self.centralwidget)

        self.retranslateUi(MainWindow)

        self.stackedWidget.setCurrentIndex(2)
        self.tabWidget.setCurrentIndex(0)


        QMetaObject.connectSlotsByName(MainWindow)
    # setupUi

    def retranslateUi(self, MainWindow):
        MainWindow.setWindowTitle(QCoreApplication.translate("MainWindow", u"\u540e\u53f0\u7ba1\u7406\u7cfb\u7edf", None))
        self.index_btn.setText(QCoreApplication.translate("MainWindow", u"  \u9996\u9875     ", None))
        self.user_manage_btn.setText(QCoreApplication.translate("MainWindow", u" \u7528\u6237\u7ba1\u7406", None))
        self.admin_info_btn.setText(QCoreApplication.translate("MainWindow", u" \u4e2a\u4eba\u4e2d\u5fc3", None))
        self.exit_btn.setText(QCoreApplication.translate("MainWindow", u" \u9000\u51fa\u7cfb\u7edf", None))
        self.label.setText(QCoreApplication.translate("MainWindow", u"\u6b22\u8fce\u6765\u5230\u540e\u53f0\u7ba1\u7406\u7cfb\u7edf", None))
        self.label_userAvatar.setText("")
        self.pushButton_mian_username.setText(QCoreApplication.translate("MainWindow", u"\u7ba1\u7406\u5458", None))
        self.label_2.setText(QCoreApplication.translate("MainWindow", u"\u6b22\u8fce\u4f7f\u7528\u57fa\u4e8e\u6df1\u5ea6\u5b66\u4e60\u7684\u884c\u4eba\u68c0\u6d4b\u540e\u53f0\u7ba1\u7406\u7cfb\u7edf", None))
        self.account_lineEdit.setText("")
        self.account_lineEdit.setPlaceholderText(QCoreApplication.translate("MainWindow", u"\u8bf7\u8f93\u5165\u8d26\u53f7", None))
        self.nikename_lineEdit.setPlaceholderText(QCoreApplication.translate("MainWindow", u"\u8bf7\u8f93\u5165\u6635\u79f0", None))
        self.select_pushButton.setText(QCoreApplication.translate("MainWindow", u"\u67e5\u8be2", None))
        self.add_pushButton.setText(QCoreApplication.translate("MainWindow", u"\u65b0\u589e", None))
        self.delete_pushButton.setText(QCoreApplication.translate("MainWindow", u"\u6279\u91cf\u5220\u9664", None))
        ___qtablewidgetitem = self.user_tableWidget.horizontalHeaderItem(1)
        ___qtablewidgetitem.setText(QCoreApplication.translate("MainWindow", u"id", None));
        ___qtablewidgetitem1 = self.user_tableWidget.horizontalHeaderItem(2)
        ___qtablewidgetitem1.setText(QCoreApplication.translate("MainWindow", u"\u5934\u50cf", None));
        ___qtablewidgetitem2 = self.user_tableWidget.horizontalHeaderItem(3)
        ___qtablewidgetitem2.setText(QCoreApplication.translate("MainWindow", u"\u8d26\u53f7", None));
        ___qtablewidgetitem3 = self.user_tableWidget.horizontalHeaderItem(4)
        ___qtablewidgetitem3.setText(QCoreApplication.translate("MainWindow", u"\u6635\u79f0", None));
        ___qtablewidgetitem4 = self.user_tableWidget.horizontalHeaderItem(5)
        ___qtablewidgetitem4.setText(QCoreApplication.translate("MainWindow", u"\u64cd\u4f5c", None));
        self.handleClose_btn.setText(QCoreApplication.translate("MainWindow", u"\u53d6\u6d88", None))
        self.label_avatar.setText("")
        self.label_25.setText(QCoreApplication.translate("MainWindow", u"\u6635\u79f0\uff1a", None))
        self.label_24.setText(QCoreApplication.translate("MainWindow", u"\u6ce8\u518c\u65f6\u95f4\uff1a", None))
        self.lineEdit_createTime.setPlaceholderText("")
        self.handleSubmit_btn.setText(QCoreApplication.translate("MainWindow", u"\u4fee\u6539", None))
        self.lineEdit_phone.setText("")
        self.lineEdit_phone.setPlaceholderText("")
        self.lineEdit_name.setText("")
        self.lineEdit_name.setPlaceholderText("")
        self.label_26.setText(QCoreApplication.translate("MainWindow", u"\u624b\u673a\u53f7\uff1a", None))
        self.tabWidget.setTabText(self.tabWidget.indexOf(self.tab_mainui_PersonalInfo), QCoreApplication.translate("MainWindow", u"\u4e2a\u4eba\u4fe1\u606f", None))
        self.label_27.setText(QCoreApplication.translate("MainWindow", u"\u65e7\u5bc6\u7801\uff1a", None))
        self.label_28.setText(QCoreApplication.translate("MainWindow", u"\u786e\u8ba4\u5bc6\u7801\uff1a", None))
        self.lineEdit_check_password.setPlaceholderText("")
        self.handleSubmit_btn_password.setText(QCoreApplication.translate("MainWindow", u"\u786e\u5b9a\u4fee\u6539", None))
        self.lineEdit_new_password.setText("")
        self.lineEdit_new_password.setPlaceholderText("")
        self.lineEdit_old_password.setText("")
        self.lineEdit_old_password.setPlaceholderText("")
        self.label_34.setText(QCoreApplication.translate("MainWindow", u"\u65b0\u5bc6\u7801\uff1a", None))
        self.label_3.setText(QCoreApplication.translate("MainWindow", u"\u5bc6\u7801\u4fee\u6539", None))
        self.tabWidget.setTabText(self.tabWidget.indexOf(self.tab_mainui_SecurityCenter), QCoreApplication.translate("MainWindow", u"\u5b89\u5168\u4e2d\u5fc3", None))
    # retranslateUi

