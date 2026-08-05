# -*- coding: utf-8 -*-

################################################################################
## Form generated from reading UI file 'untitled.ui'
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
from PySide6.QtWidgets import (QApplication, QCheckBox, QComboBox, QGridLayout,
    QMainWindow, QMenuBar, QPushButton, QSizePolicy,
    QSlider, QStatusBar, QWidget)

class Ui_MA(object):
    def setupUi(self, MA):
        if not MA.objectName():
            MA.setObjectName(u"MA")
        MA.resize(450, 400)
        self.centralwidget = QWidget(MA)
        self.centralwidget.setObjectName(u"centralwidget")
        self.gridLayoutWidget = QWidget(self.centralwidget)
        self.gridLayoutWidget.setObjectName(u"gridLayoutWidget")
        self.gridLayoutWidget.setGeometry(QRect(0, 0, 438, 58))
        self.gridLayout = QGridLayout(self.gridLayoutWidget)
        self.gridLayout.setObjectName(u"gridLayout")
        self.gridLayout.setContentsMargins(0, 0, 0, 0)
        self.startButton = QPushButton(self.gridLayoutWidget)
        self.startButton.setObjectName(u"startButton")

        self.gridLayout.addWidget(self.startButton, 0, 1, 1, 1)

        self.endButton = QPushButton(self.gridLayoutWidget)
        self.endButton.setObjectName(u"endButton")

        self.gridLayout.addWidget(self.endButton, 0, 2, 1, 1)

        self.inforButton = QPushButton(self.gridLayoutWidget)
        self.inforButton.setObjectName(u"inforButton")

        self.gridLayout.addWidget(self.inforButton, 0, 3, 1, 1)

        self.frontCheckBox = QCheckBox(self.gridLayoutWidget)
        self.frontCheckBox.setObjectName(u"frontCheckBox")

        self.gridLayout.addWidget(self.frontCheckBox, 0, 4, 1, 1)

        self.scaleComboBox = QComboBox(self.gridLayoutWidget)
        self.scaleComboBox.setObjectName(u"scaleComboBox")

        self.gridLayout.addWidget(self.scaleComboBox, 1, 2, 1, 1)

        self.comboBox = QComboBox(self.gridLayoutWidget)
        self.comboBox.setObjectName(u"comboBox")

        self.gridLayout.addWidget(self.comboBox, 1, 1, 1, 1)

        self.showMetricsComboBox = QComboBox(self.gridLayoutWidget)
        self.showMetricsComboBox.setObjectName(u"showMetricsComboBox")

        self.gridLayout.addWidget(self.showMetricsComboBox, 1, 3, 1, 1)

        self.opcSizeVerticalSlider = QSlider(self.centralwidget)
        self.opcSizeVerticalSlider.setObjectName(u"opcSizeVerticalSlider")
        self.opcSizeVerticalSlider.setGeometry(QRect(0, 60, 100, 211))
        sizePolicy = QSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        sizePolicy.setHorizontalStretch(0)
        sizePolicy.setVerticalStretch(0)
        sizePolicy.setHeightForWidth(self.opcSizeVerticalSlider.sizePolicy().hasHeightForWidth())
        self.opcSizeVerticalSlider.setSizePolicy(sizePolicy)
        self.opcSizeVerticalSlider.setMinimumSize(QSize(100, 100))
        self.opcSizeVerticalSlider.setOrientation(Qt.Orientation.Vertical)
        MA.setCentralWidget(self.centralwidget)
        self.statusbar = QStatusBar(MA)
        self.statusbar.setObjectName(u"statusbar")
        MA.setStatusBar(self.statusbar)
        self.menubar = QMenuBar(MA)
        self.menubar.setObjectName(u"menubar")
        self.menubar.setGeometry(QRect(0, 0, 450, 33))
        self.menubar.setDefaultUp(True)
        self.menubar.setNativeMenuBar(True)
        MA.setMenuBar(self.menubar)

        self.retranslateUi(MA)

        QMetaObject.connectSlotsByName(MA)
    # setupUi

    def retranslateUi(self, MA):
        MA.setWindowTitle(QCoreApplication.translate("MA", u"AWACSMARK", None))
        self.startButton.setText(QCoreApplication.translate("MA", u"\u5f00\u59cb", None))
        self.endButton.setText(QCoreApplication.translate("MA", u"\u505c\u6b62", None))
        self.inforButton.setText(QCoreApplication.translate("MA", u"\u4fe1\u606f\u67e5\u770b", None))
        self.frontCheckBox.setText(QCoreApplication.translate("MA", u"\u7f6e\u9876", None))
    # retranslateUi

