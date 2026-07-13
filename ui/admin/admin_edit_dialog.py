# -*- coding: utf-8 -*-

################################################################################
## Form generated from reading UI file 'admin_edit_dialog.ui'
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

class Ui_edit(object):
    def setupUi(self, edit):
        if not edit.objectName():
            edit.setObjectName(u"edit")
        edit.resize(336, 446)
        edit.setStyleSheet(u"QWidget#add{\n"
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
        self.cancel_btn = QPushButton(edit)
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
        self.edit_username = QLineEdit(edit)
        self.edit_username.setObjectName(u"edit_username")
        self.edit_username.setGeometry(QRect(90, 240, 201, 31))
        self.edit_username.setClearButtonEnabled(True)
        self.user_register_time = QLineEdit(edit)
        self.user_register_time.setObjectName(u"user_register_time")
        self.user_register_time.setEnabled(False)
        self.user_register_time.setGeometry(QRect(90, 290, 201, 31))
        self.user_register_time.setEchoMode(QLineEdit.Normal)
        self.user_register_time.setClearButtonEnabled(False)
        self.save_btn = QPushButton(edit)
        self.save_btn.setObjectName(u"save_btn")
        self.save_btn.setGeometry(QRect(180, 370, 71, 31))
        self.save_btn.setStyleSheet(u"")
        icon1 = QIcon()
        icon1.addFile(u"img/save.png", QSize(), QIcon.Normal, QIcon.Off)
        self.save_btn.setIcon(icon1)
        self.label = QLabel(edit)
        self.label.setObjectName(u"label")
        self.label.setGeometry(QRect(30, 240, 54, 31))
        self.label.setAlignment(Qt.AlignCenter)
        self.label_2 = QLabel(edit)
        self.label_2.setObjectName(u"label_2")
        self.label_2.setGeometry(QRect(20, 290, 54, 31))
        self.label_2.setAlignment(Qt.AlignCenter)
        self.edit_nickname = QLineEdit(edit)
        self.edit_nickname.setObjectName(u"edit_nickname")
        self.edit_nickname.setGeometry(QRect(90, 190, 201, 31))
        self.edit_nickname.setClearButtonEnabled(True)
        self.label_3 = QLabel(edit)
        self.label_3.setObjectName(u"label_3")
        self.label_3.setGeometry(QRect(30, 190, 54, 31))
        self.label_3.setAlignment(Qt.AlignCenter)
        self.label_edituser_avatar = QLabel(edit)
        self.label_edituser_avatar.setObjectName(u"label_edituser_avatar")
        self.label_edituser_avatar.setGeometry(QRect(150, 100, 61, 61))
        self.label_edituser_avatar.setPixmap(QPixmap(u":/img/img/\u5934\u50cf\u52a0\u53f7.png"))
        self.label_edituser_avatar.setScaledContents(True)
        self.label_edituser_avatar.setAlignment(Qt.AlignCenter)
        self.logo_name = QLabel(edit)
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

        self.retranslateUi(edit)

        QMetaObject.connectSlotsByName(edit)
    # setupUi

    def retranslateUi(self, edit):
        edit.setWindowTitle(QCoreApplication.translate("edit", u"\u7f16\u8f91\u7528\u6237", None))
        self.cancel_btn.setText(QCoreApplication.translate("edit", u"\u53d6\u6d88", None))
        self.edit_username.setPlaceholderText(QCoreApplication.translate("edit", u"\u8bf7\u8f93\u5165\u8d26\u53f7", None))
        self.user_register_time.setText("")
        self.user_register_time.setPlaceholderText("")
        self.save_btn.setText(QCoreApplication.translate("edit", u"\u63d0\u4ea4", None))
        self.label.setText(QCoreApplication.translate("edit", u"\u8d26\u53f7", None))
        self.label_2.setText(QCoreApplication.translate("edit", u"\u6ce8\u518c\u65f6\u95f4", None))
        self.edit_nickname.setPlaceholderText(QCoreApplication.translate("edit", u"\u8bf7\u8f93\u5165\u6635\u79f0", None))
        self.label_3.setText(QCoreApplication.translate("edit", u"\u6635\u79f0", None))
        self.label_edituser_avatar.setText("")
        self.logo_name.setText(QCoreApplication.translate("edit", u"\u7f16\u8f91\u7528\u6237", None))
    # retranslateUi

