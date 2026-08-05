# -*- coding: utf-8 -*-

################################################################################
## Form generated from reading UI file 'dialog.ui'
##
## Created by: Qt User Interface Compiler version 6.11.0
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
from PySide6.QtWidgets import (QAbstractButton, QApplication, QCheckBox, QComboBox,
    QDialog, QDialogButtonBox, QFormLayout, QFrame,
    QGridLayout, QLabel, QLineEdit, QPushButton,
    QSizePolicy, QVBoxLayout, QWidget)

class Ui_argsDialog(object):
    def setupUi(self, argsDialog):
        if not argsDialog.objectName():
            argsDialog.setObjectName(u"argsDialog")
        argsDialog.resize(400, 380)
        sizePolicy = QSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        sizePolicy.setHorizontalStretch(0)
        sizePolicy.setVerticalStretch(0)
        sizePolicy.setHeightForWidth(argsDialog.sizePolicy().hasHeightForWidth())
        argsDialog.setSizePolicy(sizePolicy)
        argsDialog.setMinimumSize(QSize(400, 380))
        argsDialog.setMaximumSize(QSize(400, 380))
        self.buttonBox = QDialogButtonBox(argsDialog)
        self.buttonBox.setObjectName(u"buttonBox")
        self.buttonBox.setGeometry(QRect(-50, 350, 341, 32))
        self.buttonBox.setOrientation(Qt.Orientation.Horizontal)
        self.buttonBox.setStandardButtons(QDialogButtonBox.StandardButton.Cancel|QDialogButtonBox.StandardButton.Ok)
        self.gridLayoutWidget = QWidget(argsDialog)
        self.gridLayoutWidget.setObjectName(u"gridLayoutWidget")
        self.gridLayoutWidget.setGeometry(QRect(0, 0, 201, 347))
        self.gridLayout = QGridLayout(self.gridLayoutWidget)
        self.gridLayout.setObjectName(u"gridLayout")
        self.gridLayout.setContentsMargins(0, 0, 0, 0)
        self.bullsEyeLat = QLineEdit(self.gridLayoutWidget)
        self.bullsEyeLat.setObjectName(u"bullsEyeLat")

        self.gridLayout.addWidget(self.bullsEyeLat, 2, 2, 1, 1)

        self.label_8 = QLabel(self.gridLayoutWidget)
        self.label_8.setObjectName(u"label_8")

        self.gridLayout.addWidget(self.label_8, 5, 1, 1, 1)

        self.label_5 = QLabel(self.gridLayoutWidget)
        self.label_5.setObjectName(u"label_5")

        self.gridLayout.addWidget(self.label_5, 3, 0, 4, 1)

        self.serverMode = QComboBox(self.gridLayoutWidget)
        self.serverMode.setObjectName(u"serverMode")

        self.gridLayout.addWidget(self.serverMode, 10, 1, 1, 2)

        self.xEdit = QLineEdit(self.gridLayoutWidget)
        self.xEdit.setObjectName(u"xEdit")

        self.gridLayout.addWidget(self.xEdit, 3, 2, 1, 1)

        self.heightEdit = QLineEdit(self.gridLayoutWidget)
        self.heightEdit.setObjectName(u"heightEdit")

        self.gridLayout.addWidget(self.heightEdit, 6, 2, 1, 1)

        self.label_4 = QLabel(self.gridLayoutWidget)
        self.label_4.setObjectName(u"label_4")

        self.gridLayout.addWidget(self.label_4, 2, 1, 1, 1)

        self.label = QLabel(self.gridLayoutWidget)
        self.label.setObjectName(u"label")
        self.label.setFrameShape(QFrame.Shape.NoFrame)

        self.gridLayout.addWidget(self.label, 0, 0, 1, 1)

        self.label_10 = QLabel(self.gridLayoutWidget)
        self.label_10.setObjectName(u"label_10")
        self.label_10.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.gridLayout.addWidget(self.label_10, 7, 0, 1, 1)

        self.label_14 = QLabel(self.gridLayoutWidget)
        self.label_14.setObjectName(u"label_14")

        self.gridLayout.addWidget(self.label_14, 10, 0, 1, 1)

        self.AWACASMARK_unit = QComboBox(self.gridLayoutWidget)
        self.AWACASMARK_unit.setObjectName(u"AWACASMARK_unit")

        self.gridLayout.addWidget(self.AWACASMARK_unit, 7, 1, 1, 2)

        self.yEdit = QLineEdit(self.gridLayoutWidget)
        self.yEdit.setObjectName(u"yEdit")

        self.gridLayout.addWidget(self.yEdit, 4, 2, 1, 1)

        self.label_11 = QLabel(self.gridLayoutWidget)
        self.label_11.setObjectName(u"label_11")
        self.label_11.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.gridLayout.addWidget(self.label_11, 8, 0, 1, 1)

        self.bullsEyeLong = QLineEdit(self.gridLayoutWidget)
        self.bullsEyeLong.setObjectName(u"bullsEyeLong")

        self.gridLayout.addWidget(self.bullsEyeLong, 1, 2, 1, 1)

        self.label_7 = QLabel(self.gridLayoutWidget)
        self.label_7.setObjectName(u"label_7")

        self.gridLayout.addWidget(self.label_7, 4, 1, 1, 1)

        self.widthEdit = QLineEdit(self.gridLayoutWidget)
        self.widthEdit.setObjectName(u"widthEdit")

        self.gridLayout.addWidget(self.widthEdit, 5, 2, 1, 1)

        self.label_2 = QLabel(self.gridLayoutWidget)
        self.label_2.setObjectName(u"label_2")

        self.gridLayout.addWidget(self.label_2, 1, 0, 2, 1)

        self.callSignLineEdit = QLineEdit(self.gridLayoutWidget)
        self.callSignLineEdit.setObjectName(u"callSignLineEdit")

        self.gridLayout.addWidget(self.callSignLineEdit, 0, 1, 1, 2)

        self.label_9 = QLabel(self.gridLayoutWidget)
        self.label_9.setObjectName(u"label_9")

        self.gridLayout.addWidget(self.label_9, 6, 1, 1, 1)

        self.RemainTime = QLineEdit(self.gridLayoutWidget)
        self.RemainTime.setObjectName(u"RemainTime")

        self.gridLayout.addWidget(self.RemainTime, 8, 1, 1, 2)

        self.label_3 = QLabel(self.gridLayoutWidget)
        self.label_3.setObjectName(u"label_3")

        self.gridLayout.addWidget(self.label_3, 1, 1, 1, 1)

        self.label_6 = QLabel(self.gridLayoutWidget)
        self.label_6.setObjectName(u"label_6")

        self.gridLayout.addWidget(self.label_6, 3, 1, 1, 1)

        self.label_13 = QLabel(self.gridLayoutWidget)
        self.label_13.setObjectName(u"label_13")

        self.gridLayout.addWidget(self.label_13, 9, 0, 1, 1)

        self.teamCodeEdit = QLineEdit(self.gridLayoutWidget)
        self.teamCodeEdit.setObjectName(u"teamCodeEdit")

        self.gridLayout.addWidget(self.teamCodeEdit, 9, 1, 1, 2)

        self.label_12 = QLabel(argsDialog)
        self.label_12.setObjectName(u"label_12")
        self.label_12.setGeometry(QRect(210, 4, 53, 21))
        self.verticalLayoutWidget = QWidget(argsDialog)
        self.verticalLayoutWidget.setObjectName(u"verticalLayoutWidget")
        self.verticalLayoutWidget.setGeometry(QRect(210, 30, 181, 86))
        self.verticalLayout = QVBoxLayout(self.verticalLayoutWidget)
        self.verticalLayout.setObjectName(u"verticalLayout")
        self.verticalLayout.setContentsMargins(0, 0, 0, 0)
        self.showEnemyCheckBox = QCheckBox(self.verticalLayoutWidget)
        self.showEnemyCheckBox.setObjectName(u"showEnemyCheckBox")
        self.showEnemyCheckBox.setToolTipDuration(-1)

        self.verticalLayout.addWidget(self.showEnemyCheckBox)

        self.showFriendCheckBox = QCheckBox(self.verticalLayoutWidget)
        self.showFriendCheckBox.setObjectName(u"showFriendCheckBox")
        self.showFriendCheckBox.setToolTipDuration(-1)

        self.verticalLayout.addWidget(self.showFriendCheckBox)

        self.serverCheckBox = QCheckBox(self.verticalLayoutWidget)
        self.serverCheckBox.setObjectName(u"serverCheckBox")
        self.serverCheckBox.setToolTipDuration(-1)

        self.verticalLayout.addWidget(self.serverCheckBox)

        self.formLayoutWidget = QWidget(argsDialog)
        self.formLayoutWidget.setObjectName(u"formLayoutWidget")
        self.formLayoutWidget.setGeometry(QRect(210, 130, 181, 115))
        self.formLayout = QFormLayout(self.formLayoutWidget)
        self.formLayout.setObjectName(u"formLayout")
        self.formLayout.setContentsMargins(0, 0, 0, 0)
        self.label_15 = QLabel(self.formLayoutWidget)
        self.label_15.setObjectName(u"label_15")
        self.label_15.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.formLayout.setWidget(0, QFormLayout.ItemRole.LabelRole, self.label_15)

        self.serverHostEdit = QLineEdit(self.formLayoutWidget)
        self.serverHostEdit.setObjectName(u"serverHostEdit")
        self.serverHostEdit.setReadOnly(False)

        self.formLayout.setWidget(0, QFormLayout.ItemRole.FieldRole, self.serverHostEdit)

        self.label_16 = QLabel(self.formLayoutWidget)
        self.label_16.setObjectName(u"label_16")
        self.label_16.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.formLayout.setWidget(1, QFormLayout.ItemRole.LabelRole, self.label_16)

        self.portEdit = QLineEdit(self.formLayoutWidget)
        self.portEdit.setObjectName(u"portEdit")
        self.portEdit.setReadOnly(False)

        self.formLayout.setWidget(1, QFormLayout.ItemRole.FieldRole, self.portEdit)

        self.testButton = QPushButton(self.formLayoutWidget)
        self.testButton.setObjectName(u"testButton")

        self.formLayout.setWidget(2, QFormLayout.ItemRole.FieldRole, self.testButton)

        self.logShow = QLabel(self.formLayoutWidget)
        self.logShow.setObjectName(u"logShow")

        self.formLayout.setWidget(3, QFormLayout.ItemRole.FieldRole, self.logShow)


        self.retranslateUi(argsDialog)
        self.buttonBox.accepted.connect(argsDialog.accept)
        self.buttonBox.rejected.connect(argsDialog.reject)

        QMetaObject.connectSlotsByName(argsDialog)
    # setupUi

    def retranslateUi(self, argsDialog):
        argsDialog.setWindowTitle(QCoreApplication.translate("argsDialog", u"\u4fe1\u606f\u8f93\u5165", None))
        self.label_8.setText(QCoreApplication.translate("argsDialog", u"\u957f", None))
#if QT_CONFIG(tooltip)
        self.label_5.setToolTip(QCoreApplication.translate("argsDialog", u"\u8f6f\u4ef6\u662f\u901a\u8fc7\u8bfb\u53d6\u5c4f\u5e55\u6587\u5b57\u8bc6\u522b\u7684\n"
"\u56e0\u6b64\u622a\u56fe\u6709\u654c\u673a\u4fe1\u606f\u7684\u5730\u65b9", None))
#endif // QT_CONFIG(tooltip)
        self.label_5.setText(QCoreApplication.translate("argsDialog", u"\u622a\u56fe\u533a\u57df", None))
        self.label_4.setText(QCoreApplication.translate("argsDialog", u"z", None))
#if QT_CONFIG(tooltip)
        self.label.setToolTip(QCoreApplication.translate("argsDialog", u"\u9884\u8b66\u673a\u53eb\u4f60\u7684\u547c\u53f7", None))
#endif // QT_CONFIG(tooltip)
        self.label.setText(QCoreApplication.translate("argsDialog", u"\u4ee3\u53f7", None))
#if QT_CONFIG(tooltip)
        self.label_10.setToolTip(QCoreApplication.translate("argsDialog", u"\u7ed9\u4f60\u62a5\u7684\u654c\u673a\u4fe1\u606f\u662f\u4ec0\u4e48\u5355\u4f4d\u7684\uff0c\u6d77\u91cc\u3001\u516c\u91cc\uff1f", None))
#endif // QT_CONFIG(tooltip)
        self.label_10.setText(QCoreApplication.translate("argsDialog", u"\u9884\u8b66\u673a\n"
"\u5355\u4f4d", None))
#if QT_CONFIG(tooltip)
        self.label_14.setToolTip(QCoreApplication.translate("argsDialog", u"\u4f20\u7edf\u7684\u5de6\u4e0a\u89d2\u9884\u8b66\u673a\u548cSPS\u670d\u52a1\u5668\u53f3\u4e0a\u89d2\u62a5\u70b9", None))
#endif // QT_CONFIG(tooltip)
        self.label_14.setText(QCoreApplication.translate("argsDialog", u"\u670d\u52a1\u5668", None))
#if QT_CONFIG(tooltip)
        self.label_11.setToolTip(QCoreApplication.translate("argsDialog", u"\u654c\u673a\u5728\u5c4f\u5e55\u6d88\u5931\u7684\u65f6\u95f4", None))
#endif // QT_CONFIG(tooltip)
        self.label_11.setText(QCoreApplication.translate("argsDialog", u"\u654c\u673a\u6b8b\n"
"\u7559\u65f6\u95f4", None))
        self.bullsEyeLong.setText("")
        self.label_7.setText(QCoreApplication.translate("argsDialog", u"y", None))
#if QT_CONFIG(tooltip)
        self.label_2.setToolTip(QCoreApplication.translate("argsDialog", u"\u5b57\u9762\u610f\u601d", None))
#endif // QT_CONFIG(tooltip)
        self.label_2.setText(QCoreApplication.translate("argsDialog", u"\u9776\u773c\u5750\u6807", None))
        self.label_9.setText(QCoreApplication.translate("argsDialog", u"\u9ad8", None))
        self.label_3.setText(QCoreApplication.translate("argsDialog", u"x", None))
        self.label_6.setText(QCoreApplication.translate("argsDialog", u"x", None))
#if QT_CONFIG(tooltip)
        self.label_13.setToolTip(QCoreApplication.translate("argsDialog", u"\u548c\u5176\u4ed6\u4eba\u4ee3\u7801\u4e00\u6837\uff0c\u4f1a\u663e\u793a\u5bf9\u5e94\u5c0f\u961f", None))
#endif // QT_CONFIG(tooltip)
        self.label_13.setText(QCoreApplication.translate("argsDialog", u"\u5c0f\u961f\u4ee3\u7801", None))
#if QT_CONFIG(tooltip)
        self.label_12.setToolTip(QCoreApplication.translate("argsDialog", u"\u5982\u679c\u4e0d\u663e\u793a\u654c\u673a\uff0c\u5c31\u4e0d\u622a\u56fe\u8bc6\u522b\uff0c\u51cf\u5c11\u5360\u7528\n"
"\u662f\u5426\u663e\u793a\u961f\u53cb\n"
"\u8fdc\u7a0b\u670d\u52a1\u5668\u5426\u7684\u8bdd\u5c31\u7528\u4e0b\u9762\u7684", None))
#endif // QT_CONFIG(tooltip)
        self.label_12.setText(QCoreApplication.translate("argsDialog", u"\u529f\u80fd\uff1a", None))
#if QT_CONFIG(tooltip)
        self.showEnemyCheckBox.setToolTip("")
#endif // QT_CONFIG(tooltip)
        self.showEnemyCheckBox.setText(QCoreApplication.translate("argsDialog", u"\u654c\u673a\u663e\u793a", None))
#if QT_CONFIG(tooltip)
        self.showFriendCheckBox.setToolTip("")
#endif // QT_CONFIG(tooltip)
        self.showFriendCheckBox.setText(QCoreApplication.translate("argsDialog", u"\u961f\u53cb\u663e\u793a", None))
#if QT_CONFIG(tooltip)
        self.serverCheckBox.setToolTip(QCoreApplication.translate("argsDialog", u"\u8fdc\u7a0b\u670d\u52a1\u5668\u5426\u7684\u8bdd\u5c31\u7528\u4e0b\u9762\u7684", None))
#endif // QT_CONFIG(tooltip)
        self.serverCheckBox.setText(QCoreApplication.translate("argsDialog", u"\u9ed8\u8ba4\u670d\u52a1\u5668", None))
        self.label_15.setText(QCoreApplication.translate("argsDialog", u"\u670d\u52a1\u5668\n"
"\u5730\u5740\uff1a", None))
        self.label_16.setText(QCoreApplication.translate("argsDialog", u"\u7aef\u53e3\uff1a", None))
        self.testButton.setText(QCoreApplication.translate("argsDialog", u"\u670d\u52a1\u5668\u8fde\u901a\u6d4b\u8bd5", None))
        self.logShow.setText("")
    # retranslateUi

