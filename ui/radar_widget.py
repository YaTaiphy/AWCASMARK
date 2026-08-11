# -*- coding: utf-8 -*-
"""雷达绘制控件 — 独立的 QWidget，仅在自己的区域内绘制雷达图。

将 paintEvent 从 QMainWindow 移到该控件，避免与按钮/滑块区域重叠。
"""

from PySide6.QtWidgets import QWidget
from PySide6.QtGui import QPainter

from radar.renderer import RadarRenderer
from config import config


class RadarWidget(QWidget):
    """雷达绘制控件 — 拥有独立的 paintEvent，绘制范围限定于控件几何区域。"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.renderer = RadarRenderer()

        # 由 MainWindow 在刷新时写入
        self.plane_data = {"heading": 270, "x": 0, "y": 2000, "z": 0, "height": 0}
        self.message_dic = {}
        self.bullseye_dic = {}
        self.team_members = []
        self.display_mode = 0       # comboBox 索引
        self.scale_index = 0        # scaleComboBox 索引

        # 避免透明背景导致看不见
        self.setAutoFillBackground(True)
        from PySide6.QtGui import QPalette, QColor
        pal = self.palette()
        pal.setColor(QPalette.Window, QColor(0, 0, 0))
        self.setPalette(pal)

    def update_data(self, plane_data, message_dic, bullseye_dic, team_members,
                    display_mode, scale_index):
        """由 MainWindow 调用，更新绘制数据并触发重绘。"""
        self.plane_data = plane_data
        self.message_dic = message_dic
        self.bullseye_dic = bullseye_dic
        self.team_members = team_members
        self.display_mode = display_mode
        self.scale_index = scale_index
        self.update()  # 触发 paintEvent

    def paintEvent(self, event):
        """仅在本控件区域内绘制雷达图。"""
        with QPainter(self) as painter:
            self.renderer.render(
                painter=painter,
                mode=self.display_mode,
                plane_data=self.plane_data,
                message_dic=self.message_dic,
                bullseye_dic=self.bullseye_dic,
                team_members=self.team_members,
                width=self.width(),
                height=self.height(),
                scale_index=self.scale_index,
                display_metric=config.show_metrics,
            )
