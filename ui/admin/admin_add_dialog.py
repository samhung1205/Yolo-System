# -*- coding: utf-8 -*-

################################################################################
## Form generated from reading UI file 'admin_add_dialog.ui'
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
from PySide6.QtWidgets import (QApplication, QLabel, QLineEdit, QPushButton,
    QSizePolicy, QWidget)
import admin_icon_rc

class Ui_add(object):
    def setupUi(self, add):
        if not add.objectName():
            add.setObjectName(u"add")
        add.resize(336, 446)
        add.setStyleSheet(u"QWidget#add{\n"
"	background-color: rgb(255, 255, 255);\n"
"}\n"
"QLineEdit{\n"
"border:1px solid rgb(190, 190, 190);\n"
"}\n"
"QPushButton{\n"
"	background-color: rgb(52, 148, 254);\n"
"    font: 16px \"Arial\";\n"
"	color: rgb(255, 255, 255);\n"
"    border:none;\n"
"    width:150px;\n"
"    height:35px;\n"
"    padding-left:5px;\n"
"    padding-right:5px;\n"
"}\n"
"QPushButton:hover{\n"
"	background-color: rgb(86, 164, 251);\n"
"}")
        self.cancel_btn = QPushButton(add)
        self.cancel_btn.setObjectName(u"cancel_btn")
        self.cancel_btn.setGeometry(QRect(90, 370, 71, 31))
        self.cancel_btn.setStyleSheet(u"QPushButton{\n"
"background-color: rgb(255, 255, 255);\n"
"color: rgb(18, 18, 18);\n"
"border:1px solid #CBD5E0;\n"
"}\n"
"QPushButton:hover{\n"
"	background-color: rgb(232, 242, 251);\n"
"	color: rgb(52, 148, 254);\n"
"}")
        icon = QIcon()
        icon.addFile(u"img/cancel.png", QSize(), QIcon.Normal, QIcon.Off)
        self.cancel_btn.setIcon(icon)
        self.add_username = QLineEdit(add)
        self.add_username.setObjectName(u"add_username")
        self.add_username.setGeometry(QRect(90, 240, 201, 31))
        self.add_username.setClearButtonEnabled(True)
        self.add_password = QLineEdit(add)
        self.add_password.setObjectName(u"add_password")
        self.add_password.setGeometry(QRect(90, 290, 201, 31))
        self.add_password.setEchoMode(QLineEdit.Password)
        self.add_password.setClearButtonEnabled(True)
        self.save_btn = QPushButton(add)
        self.save_btn.setObjectName(u"save_btn")
        self.save_btn.setGeometry(QRect(180, 370, 71, 31))
        self.save_btn.setStyleSheet(u"")
        icon1 = QIcon()
        icon1.addFile(u"img/save.png", QSize(), QIcon.Normal, QIcon.Off)
        self.save_btn.setIcon(icon1)
        self.label = QLabel(add)
        self.label.setObjectName(u"label")
        self.label.setGeometry(QRect(30, 240, 54, 31))
        self.label.setAlignment(Qt.AlignCenter)
        self.label_2 = QLabel(add)
        self.label_2.setObjectName(u"label_2")
        self.label_2.setGeometry(QRect(30, 290, 54, 31))
        self.label_2.setAlignment(Qt.AlignCenter)
        self.add_nickname = QLineEdit(add)
        self.add_nickname.setObjectName(u"add_nickname")
        self.add_nickname.setGeometry(QRect(90, 190, 201, 31))
        self.add_nickname.setClearButtonEnabled(True)
        self.label_3 = QLabel(add)
        self.label_3.setObjectName(u"label_3")
        self.label_3.setGeometry(QRect(30, 190, 54, 31))
        self.label_3.setAlignment(Qt.AlignCenter)
        self.label_adduser_avatar = QLabel(add)
        self.label_adduser_avatar.setObjectName(u"label_adduser_avatar")
        self.label_adduser_avatar.setGeometry(QRect(150, 100, 61, 61))
        self.label_adduser_avatar.setPixmap(QPixmap(u":/img/img/\u5934\u50cf\u52a0\u53f7.png"))
        self.label_adduser_avatar.setScaledContents(True)
        self.label_adduser_avatar.setAlignment(Qt.AlignCenter)
        self.logo_name = QLabel(add)
        self.logo_name.setObjectName(u"logo_name")
        self.logo_name.setGeometry(QRect(100, 20, 171, 41))
        palette = QPalette()
        brush = QBrush(QColor(0, 255, 0, 255))
        brush.setStyle(Qt.SolidPattern)
        palette.setBrush(QPalette.Active, QPalette.WindowText, brush)
        palette.setBrush(QPalette.Inactive, QPalette.WindowText, brush)
        brush1 = QBrush(QColor(120, 120, 120, 255))
        brush1.setStyle(Qt.SolidPattern)
        palette.setBrush(QPalette.Disabled, QPalette.WindowText, brush1)
        self.logo_name.setPalette(palette)
        self.logo_name.setStyleSheet(u"font: 20px \"Bauhaus 93\";")
        self.logo_name.setAlignment(Qt.AlignCenter)

        self.retranslateUi(add)

        QMetaObject.connectSlotsByName(add)
    # setupUi

    def retranslateUi(self, add):
        add.setWindowTitle(QCoreApplication.translate("add", u"\u65b0\u589e\u7528\u6237", None))
        self.cancel_btn.setText(QCoreApplication.translate("add", u"\u53d6\u6d88", None))
        self.add_username.setPlaceholderText(QCoreApplication.translate("add", u"\u8bf7\u8f93\u5165\u8d26\u53f7", None))
        self.add_password.setText("")
        self.add_password.setPlaceholderText(QCoreApplication.translate("add", u"\u8bf7\u8f93\u5165\u5bc6\u7801", None))
        self.save_btn.setText(QCoreApplication.translate("add", u"\u4fdd\u5b58", None))
        self.label.setText(QCoreApplication.translate("add", u"\u8d26\u53f7", None))
        self.label_2.setText(QCoreApplication.translate("add", u"\u5bc6\u7801", None))
        self.add_nickname.setPlaceholderText(QCoreApplication.translate("add", u"\u8bf7\u8f93\u5165\u6635\u79f0", None))
        self.label_3.setText(QCoreApplication.translate("add", u"\u6635\u79f0", None))
        self.label_adduser_avatar.setText("")
        self.logo_name.setText(QCoreApplication.translate("add", u"\u65b0\u589e\u7528\u6237", None))
    # retranslateUi

