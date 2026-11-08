# -*- coding: utf-8 -*-
"""主窗口 — 从 main.py Winform 提取。

职责：
- UI 控件初始化（委托 Ui_MA.setupUi）
- paintEvent → RadarRenderer
- 定时器管理（3 个 QTimer）
- 线程管理（UDP / OCR / Team 各一个持久线程）
- 信号/槽连接
- 简要显示模式（全屏雷达，无边框 + 可拖动 + 可调尺寸）
"""

import time
from PySide6.QtWidgets import (
    QMainWindow, QMessageBox, QPushButton, QSlider, QLabel, QToolBar,
    QSizeGrip, QCheckBox,
)
from PySide6.QtCore import Qt, QThread, QTimer, Signal, QRect, QMetaObject
from PySide6.QtGui import QAction

from log import get_logger

logger = get_logger(__name__)

from window import Ui_MA
from config import config
from constants import (
    TIMER_OCR_MS, TIMER_SCREENSHOT_MS, TIMER_TEAM_MS,
    DEFAULT_SERVER_HOST, DEFAULT_SERVER_PORT,
    DISPLAY_MODE_NGAS, DISPLAY_MODE_SA, DISPLAY_MODE_CENTER_SA,
    OPACITY_MIN, OPACITY_MAX,
)
from network.udp_listener import SocketWorker
from network.http_client import check_server_health
from worker.ocr_worker import OCRWorker
from worker.team_worker import TeamWorker
from ocr.screenshot import take_screenshot
from ui.radar_widget import RadarWidget


class MainWindow(QMainWindow, Ui_MA):
    """主窗口 — 精简的 UI + 信号连接 + paintEvent 委托。"""

    # ---- 边沿拖拽调尺寸阈值 (px) ----
    _RESIZE_MARGIN = 8

    def __init__(self, parent=None, center_x=200, center_y=200, num_circles=5):
        super().__init__(parent)
        self.setupUi(self)

        # ---- 统一暗色主题 ----
        self.setStyleSheet("""
            QMainWindow, QWidget#centralwidget {
                background-color: #0a0a0a;
            }
            QPushButton {
                background-color: #2a2a2a;
                color: #cccccc;
                border: 1px solid #444;
                border-radius: 3px;
                padding: 4px 10px;
            }
            QPushButton:hover {
                background-color: #3a3a3a;
            }
            QPushButton:disabled {
                color: #666;
            }
            QComboBox {
                background-color: #2a2a2a;
                color: #cccccc;
                border: 1px solid #444;
            }
            QCheckBox {
                color: #cccccc;
            }
        """)

        # ---- 基本设置 ----
        self.resize(560, 420)
        self.comboBox.addItems(["中心", "直对", "中心直对"])
        self.comboBox.currentIndexChanged.connect(self._refresh_radar)

        # scaleComboBox 保留用于数据传递，但 UI 上用浮动滑块替代
        self.scaleComboBox.addItems(["50km", "100km", "200km"])
        self.scaleComboBox.currentIndexChanged.connect(self._refresh_radar)

        self.showMetricsComboBox.addItems(["km", "nm"])
        self.showMetricsComboBox.currentIndexChanged.connect(self._metrics_changed)

        self.center_x = center_x
        self.center_y = center_y
        self.num_circles = num_circles

        # ---- 信号连接 ----
        self.opcSizeVerticalSlider.setMinimum(OPACITY_MIN)
        self.opcSizeVerticalSlider.setMaximum(OPACITY_MAX)
        self.opcSizeVerticalSlider.setValue(100)
        self.opcSizeVerticalSlider.valueChanged.connect(self._change_opacity)

        self.startButton.clicked.connect(self._toggle_mission)
        # endButton 保留但隐藏 — 改为单按钮切换，不再使用两个独立按钮
        self.endButton.hide()

        self.inforButton.clicked.connect(self._show_settings)

        # ---- 功能区工具栏（替代 gridLayout） ----
        self._setup_toolbar()

        # ---- 隐藏原始 gridLayout + 废弃控件 ----
        self.gridLayoutWidget.hide()
        self.gridLayoutWidget.setFixedSize(0, 0)  # 彻底消除黑条
        self.scaleComboBox.hide()   # UI 用右侧浮动滑块替代
        self.frontCheckBox.hide()   # 移至雷达区浮动 (endButton 在 _setup_toolbar 中 hide)

        # ---- 左侧浮动控件：透明度滑块 ----
        self._opacity_slider = self.opcSizeVerticalSlider
        # 缩小滑块宽度
        self._opacity_slider.setFixedWidth(24)
        self._opacity_slider.setStyleSheet("""
            QSlider::groove:vertical {
                background: rgba(50,50,50,160);
                width: 4px;
                border-radius: 2px;
            }
            QSlider::handle:vertical {
                background: #5a8aba;
                height: 14px;
                margin: 0 -4px;
                border-radius: 3px;
            }
            QSlider::sub-page:vertical {
                background: rgba(90,138,186,100);
                border-radius: 2px;
            }
        """)

        # ---- 右侧浮动控件：比例尺滑块 ----
        self._scale_slider = QSlider(Qt.Orientation.Vertical, self.centralwidget)
        self._scale_slider.setMinimum(0)
        self._scale_slider.setMaximum(2)
        self._scale_slider.setValue(0)
        self._scale_slider.setTickPosition(QSlider.TickPosition.TicksLeft)
        self._scale_slider.setTickInterval(1)
        self._scale_slider.setFixedWidth(30)
        self._scale_slider.setStyleSheet("""
            QSlider::groove:vertical {
                background: rgba(50,50,50,160);
                width: 4px;
                border-radius: 2px;
            }
            QSlider::handle:vertical {
                background: #c08030;
                height: 14px;
                margin: 0 -4px;
                border-radius: 3px;
            }
            QSlider::sub-page:vertical {
                background: rgba(192,128,48,100);
                border-radius: 2px;
            }
        """)
        self._scale_slider.valueChanged.connect(self._on_scale_slider_changed)

        self._scale_label = QLabel("50km", self.centralwidget)
        self._scale_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._scale_label.setStyleSheet(
            "color: #ffcc66; font-size: 10px; font-weight: bold; background: transparent;"
        )
        self._scale_label.setFixedWidth(36)

        # ---- 置顶复选框（浮动于雷达区左上角） ----
        self._topmost_check = QCheckBox("置顶", self.centralwidget)
        self._topmost_check.setStyleSheet("""
            QCheckBox {
                color: #cccccc;
                background: rgba(20,20,20,160);
                border-radius: 2px;
                padding: 2px 6px;
            }
        """)
        self._topmost_check.stateChanged.connect(self._toggle_topmost)

        # ---- 飞行数据面板切换复选框（浮动于雷达区左上角） ----
        self._flight_data_check = QCheckBox("数据", self.centralwidget)
        self._flight_data_check.setStyleSheet("""
            QCheckBox {
                color: #cccccc;
                background: rgba(20,20,20,160);
                border-radius: 2px;
                padding: 2px 6px;
            }
        """)
        self._flight_data_check.stateChanged.connect(self._toggle_flight_data)

        # ---- 简要模式控件 ----
        self._compact_restore_btn = QPushButton("恢复", self.centralwidget)
        self._compact_restore_btn.setFixedSize(50, 24)
        self._compact_restore_btn.setStyleSheet("""
            QPushButton {
                background-color: rgba(40,40,40,200);
                color: #aaa;
                border: 1px solid #555;
                border-radius: 3px;
                font-size: 11px;
            }
            QPushButton:hover {
                background-color: rgba(60,60,60,220);
                color: #fff;
            }
        """)
        self._compact_restore_btn.clicked.connect(self._toggle_compact_mode)
        self._compact_restore_btn.hide()

        # 简要模式底部比例尺 (水平)
        self._compact_scale_slider = QSlider(Qt.Orientation.Horizontal, self.centralwidget)
        self._compact_scale_slider.setMinimum(0)
        self._compact_scale_slider.setMaximum(2)
        self._compact_scale_slider.setValue(0)
        self._compact_scale_slider.setFixedHeight(30)
        self._compact_scale_slider.setStyleSheet("""
            QSlider::groove:horizontal {
                background: rgba(50,50,50,180);
                height: 6px;
                border-radius: 3px;
            }
            QSlider::handle:horizontal {
                background: #c08030;
                width: 16px;
                margin: -5px 0;
                border-radius: 4px;
            }
            QSlider::sub-page:horizontal {
                background: rgba(192,128,48,120);
                border-radius: 3px;
            }
        """)
        self._compact_scale_slider.valueChanged.connect(self._on_compact_scale_changed)
        self._compact_scale_slider.hide()

        self._compact_scale_label = QLabel("50km", self.centralwidget)
        self._compact_scale_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._compact_scale_label.setStyleSheet(
            "color: #ffcc66; font-size: 12px; font-weight: bold; background: transparent;"
        )
        self._compact_scale_label.setFixedHeight(20)
        self._compact_scale_label.hide()

        # 简要模式尺寸调节手柄
        self._compact_size_grip = QSizeGrip(self.centralwidget)
        self._compact_size_grip.setFixedSize(16, 16)
        self._compact_size_grip.setStyleSheet(
            "background: rgba(60,60,60,180); border-radius: 2px;"
        )
        self._compact_size_grip.hide()

        # ---- 内部状态 ----
        self._compact_mode = False
        self._drag_pos = None
        self._resize_edge = None       # 调尺寸命中边: 'n','s','e','w','ne','nw','se','sw'
        self._resize_geom = None       # 开始调尺寸时的窗口几何
        self._resize_start = None      # 开始调尺寸时的全局鼠标位置
        self._mission_running = False
        self._refresh_pending = False  # 刷新节流: resize/UDP 高频更新时合并请求

        # ---- 数据状态 ----
        self.plane_data = {
            "heading": 270, "x": 0, "y": 2000, "z": 0, "height": 0,
            "pitch": 0, "alt_bar": 0, "alt_rad": 0,
            "true_air_speed": 0, "indicated_air_speed": 0,
        }
        self.message_dic = {}
        self.bullseye_dic = {}
        self.team_members = []
        self.screen_shot_list = []
        self.args_ready = False

        # ---- 雷达控件 ----
        self.radar_widget = RadarWidget(self.centralwidget)
        self._layout_radar_widget()
        self.radar_widget.lower()

        # ---- 初始布局 ----
        self._layout_side_controls()

        # ---- 定时器 ----
        self._timer_ocr = QTimer(self)
        self._timer_ocr.timeout.connect(self._tick_ocr)
        self._timer_screen = QTimer(self)
        self._timer_screen.timeout.connect(self._tick_screenshot)
        self._timer_team = QTimer(self)
        self._timer_team.timeout.connect(self._tick_team)

        # ---- 工作线程 ----
        self._udp_thread = None
        self._udp_worker = None
        self._ocr_thread = None
        self._ocr_worker = None
        self._team_thread = None
        self._team_worker = None

        # ---- 配置迁移 ----
        self._migrate_config()

    # =========================================================================
    # 配置
    # =========================================================================

    def _migrate_config(self):
        import ast
        from pathlib import Path

        cfg_path = config.config_path()
        json_path = Path(str(cfg_path).replace(".txt", ".json"))

        if json_path.exists():
            config.load_from_disk()
        elif cfg_path.exists():
            try:
                raw = cfg_path.read_text(encoding="utf-8")
                data = ast.literal_eval(raw)
                if isinstance(data, dict):
                    config._apply_dict(data)
                config.save_to_disk()
                logger.info("旧配置已迁移到 JSON 格式")
            except Exception as exc:
                logger.warning("旧配置迁移失败: %s", exc)
        else:
            config.load_from_disk()

    # =========================================================================
    # 工具栏
    # =========================================================================

    def _setup_toolbar(self):
        """创建功能区工具栏。

        布局: [简要] [▶开始/■停止] [信息查看] | 模式:[▾] 单位:[▾]
        注: 比例尺改为右侧浮动垂直滑块，置顶改为雷达区浮动复选框
        """
        self._toolbar = QToolBar("功能区", self)
        self._toolbar.setObjectName("功能区")
        self._toolbar.setMovable(False)
        self._toolbar.setFloatable(False)
        self._toolbar.setStyleSheet("""
            QToolBar {
                background-color: #141414;
                border-bottom: 1px solid #333;
                spacing: 4px;
                padding: 2px 4px;
            }
            QToolBar QPushButton {
                background-color: #2a2a2a;
                color: #cccccc;
                border: 1px solid #444;
                border-radius: 3px;
                padding: 4px 12px;
                min-width: 48px;
            }
            QToolBar QPushButton:hover {
                background-color: #3a3a3a;
            }
            QToolBar QPushButton:disabled {
                color: #666;
            }
            QToolBar QComboBox {
                background-color: #2a2a2a;
                color: #cccccc;
                border: 1px solid #444;
                min-width: 70px;
                padding: 2px 4px;
            }
            QToolBar QLabel {
                color: #999;
                font-size: 11px;
                padding: 0 2px;
            }
        """)
        self.addToolBar(Qt.ToolBarArea.TopToolBarArea, self._toolbar)

        # 从 gridLayout 移除控件
        for w in [self.startButton, self.endButton, self.inforButton,
                   self.comboBox, self.scaleComboBox, self.showMetricsComboBox]:
            self.gridLayout.removeWidget(w)

        # 简要按钮
        self.compactButton = QPushButton("简要")
        self.compactButton.setToolTip("切换简要显示模式（仅雷达图 + 比例尺）")
        self.compactButton.clicked.connect(self._toggle_compact_mode)

        # 操作按钮组（开始/停止合并为单按钮切换）
        self._toolbar.addWidget(self.compactButton)
        self._toolbar.addWidget(self.startButton)  # 即「开始」也即「停止」（点击切换）
        self._toolbar.addWidget(self.inforButton)

        self._toolbar.addSeparator()

        # 设置下拉框组 (无比例尺 — 已改为右侧浮动滑块)
        for label_text, widget in [
            ("模式", self.comboBox),
            ("单位", self.showMetricsComboBox),
        ]:
            lbl = QLabel(f"{label_text}:")
            self._toolbar.addWidget(lbl)
            self._toolbar.addWidget(widget)

    # =========================================================================
    # 布局
    # =========================================================================

    def _layout_radar_widget(self):
        """雷达控件填充整个 centralwidget（Qt 已将 toolbar/menubar 排除在外）。"""
        self.radar_widget.setGeometry(
            0, 0,
            self.centralwidget.width(),
            self.centralwidget.height(),
        )

    def _layout_side_controls(self):
        """定位左右浮动控件（坐标相对于 centralwidget，原点已在 toolbar 下方）。"""
        w = self.centralwidget.width()
        h = self.centralwidget.height()

        # 透明度滑块 — 最左侧，紧贴左边缘
        slider_h = max(80, h - 20)
        self._opacity_slider.setFixedHeight(slider_h)
        self._opacity_slider.move(4, (h - slider_h) // 2)
        self._opacity_slider.raise_()

        # 比例尺滑块 — 最右侧
        scale_h = max(80, h - 40)
        self._scale_slider.setFixedHeight(scale_h)
        self._scale_slider.move(w - 34, (h - scale_h) // 2)
        self._scale_slider.raise_()

        # 比例尺标签 — 滑块下方
        self._scale_label.move(w - 36, (h - scale_h) // 2 + scale_h + 2)
        self._scale_label.raise_()

        # 置顶复选框 — 雷达区左上角内侧 (x=32 避开透明度滑块 x=4~28)
        self._topmost_check.move(32, 4)
        self._topmost_check.raise_()

        # 飞行数据复选框 — 置顶下方
        self._flight_data_check.move(32, 28)
        self._flight_data_check.raise_()

    def _refresh_radar(self):
        """推数据到雷达控件并重绘。"""
        self.radar_widget.update_data(
            plane_data=self.plane_data,
            message_dic=self.message_dic,
            bullseye_dic=self.bullseye_dic,
            team_members=self.team_members,
            display_mode=self.comboBox.currentIndex(),
            scale_index=self.scaleComboBox.currentIndex(),
            show_data_panel=self._flight_data_check.isChecked(),
        )

    def _schedule_refresh(self):
        """合并短时间内多次刷新请求（resize / UDP 高频更新）。

        用 16ms 单次定时器将频繁的 refresh 合并为 ~60fps 的实际重绘，
        避免 resize 拖动或高频 UDP 报文时每个事件都触发完整雷达渲染。
        """
        if not self._refresh_pending:
            self._refresh_pending = True
            QTimer.singleShot(16, self._do_pending_refresh)

    def _do_pending_refresh(self):
        """执行被合并后的实际刷新。"""
        self._refresh_pending = False
        self._refresh_radar()

    # =========================================================================
    # 窗口控制
    # =========================================================================

    def _toggle_topmost(self, state):
        if state == Qt.CheckState.Checked.value:
            self.setWindowFlag(Qt.WindowType.WindowStaysOnTopHint, True)
        else:
            self.setWindowFlag(Qt.WindowType.WindowStaysOnTopHint, False)
        self.show()

    def _toggle_flight_data(self, state):
        """切换飞行数据面板 / 雷达界面。"""
        self.radar_widget.show_data_panel = (
            state == Qt.CheckState.Checked.value
        )
        self._refresh_radar()

    def _change_opacity(self, value):
        self.setWindowOpacity(value / 100.0)

    def _on_scale_slider_changed(self, value):
        """右侧比例尺滑块变化 → 同步到隐藏的 scaleComboBox。"""
        self.scaleComboBox.setCurrentIndex(value)
        self._update_scale_label()
        self._refresh_radar()

    def _update_scale_label(self):
        labels = {0: "50km", 1: "100km", 2: "200km"}
        if config.show_metrics == "nm":
            labels = {0: "25nm", 1: "50nm", 2: "100nm"}
        self._scale_label.setText(labels.get(self._scale_slider.value(), ""))

    # =========================================================================
    # 鼠标事件 — 拖动 + 调尺寸
    # =========================================================================

    def _detect_resize_edge(self, pos):
        """返回命中的边沿名称，若未命中返回 None。"""
        r = self.rect()
        x, y, w, h = pos.x(), pos.y(), r.width(), r.height()
        m = self._RESIZE_MARGIN

        n = y <= m
        s = y >= h - m
        e = x >= w - m
        ww = x <= m

        if n and e:  return "ne"
        if n and ww: return "nw"
        if s and e:  return "se"
        if s and ww: return "sw"
        if n:        return "n"
        if s:        return "s"
        if e:        return "e"
        if ww:       return "w"
        return None

    def _resize_cursor(self, edge):
        """根据边沿返回对应光标形状。"""
        cursors = {
            "n":  Qt.CursorShape.SizeVerCursor,
            "s":  Qt.CursorShape.SizeVerCursor,
            "e":  Qt.CursorShape.SizeHorCursor,
            "w":  Qt.CursorShape.SizeHorCursor,
            "ne": Qt.CursorShape.SizeBDiagCursor,
            "sw": Qt.CursorShape.SizeBDiagCursor,
            "nw": Qt.CursorShape.SizeFDiagCursor,
            "se": Qt.CursorShape.SizeFDiagCursor,
        }
        return cursors.get(edge, Qt.CursorShape.ArrowCursor)

    def mousePressEvent(self, event):
        if not self._compact_mode:
            super().mousePressEvent(event)
            return

        if event.button() == Qt.MouseButton.LeftButton:
            local = event.position().toPoint()
            edge = self._detect_resize_edge(local)
            if edge:
                # 调尺寸
                self._resize_edge = edge
                self._resize_geom = self.geometry()
                self._resize_start = event.globalPosition().toPoint()
                event.accept()
                return
            else:
                # 拖动窗口
                self._drag_pos = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
                event.accept()
                return

        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if not self._compact_mode:
            super().mouseMoveEvent(event)
            return

        if self._resize_edge and self._resize_geom and self._resize_start:
            # 调尺寸
            delta = event.globalPosition().toPoint() - self._resize_start
            g = QRect(self._resize_geom)
            edge = self._resize_edge

            if "n" in edge:
                g.setTop(g.top() + delta.y())
            if "s" in edge:
                g.setBottom(g.bottom() + delta.y())
            if "w" in edge:
                g.setLeft(g.left() + delta.x())
            if "e" in edge:
                g.setRight(g.right() + delta.x())

            # 最小尺寸限制
            if g.width() < 200:
                if "w" in edge:
                    g.setLeft(g.right() - 200)
                else:
                    g.setRight(g.left() + 200)
            if g.height() < 150:
                if "n" in edge:
                    g.setTop(g.bottom() - 150)
                else:
                    g.setBottom(g.top() + 150)

            self.setGeometry(g)
            event.accept()
            return

        if self._drag_pos is not None:
            self.move(event.globalPosition().toPoint() - self._drag_pos)
            event.accept()
            return

        # 更新光标形状 (仅在未拖拽时)
        local = event.position().toPoint()
        edge = self._detect_resize_edge(local)
        self.setCursor(self._resize_cursor(edge) if edge else Qt.CursorShape.ArrowCursor)

        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        if self._compact_mode and event.button() == Qt.MouseButton.LeftButton:
            self._drag_pos = None
            self._resize_edge = None
            self._resize_geom = None
            self._resize_start = None
            event.accept()
            return
        super().mouseReleaseEvent(event)

    # =========================================================================
    # 简要显示模式
    # =========================================================================

    def _toggle_compact_mode(self):
        if self._compact_mode:
            self._exit_compact_mode()
        else:
            self._enter_compact_mode()

    def _enter_compact_mode(self):
        self._compact_mode = True

        # 隐藏标准界面
        self.menubar.hide()
        self.statusbar.hide()
        self._toolbar.hide()
        self._opacity_slider.hide()
        self._scale_slider.hide()
        self._scale_label.hide()
        self._topmost_check.hide()
        self._flight_data_check.hide()

        # 无边框 + 可调尺寸（保留置顶属性）
        self._old_flags = self.windowFlags()
        flags = Qt.WindowType.FramelessWindowHint
        if self._topmost_check.isChecked():
            flags |= Qt.WindowType.WindowStaysOnTopHint
        self.setWindowFlags(flags)
        self.setCursor(Qt.CursorShape.ArrowCursor)

        # 布局浮动控件
        self._layout_compact_controls()

        # 显示浮动控件
        self._compact_restore_btn.show()
        self._compact_scale_slider.show()
        self._compact_scale_label.show()
        self._compact_size_grip.show()

        # 雷达铺满
        self.radar_widget.setGeometry(0, 0, self.width(), self.height())
        self.radar_widget.raise_()
        self._compact_restore_btn.raise_()
        self._compact_scale_slider.raise_()
        self._compact_scale_label.raise_()
        self._compact_size_grip.raise_()

        # 同步滑块值
        self._compact_scale_slider.setValue(self._scale_slider.value())
        self._update_compact_scale_label()

        self.compactButton.setText("恢复")
        self.show()

    def _exit_compact_mode(self):
        self._compact_mode = False

        # 恢复窗口标志
        self.setWindowFlags(self._old_flags)
        self.setCursor(Qt.CursorShape.ArrowCursor)

        # 显示所有控件
        self.menubar.show()
        self.statusbar.show()
        self._toolbar.show()
        self._opacity_slider.show()
        self._scale_slider.show()
        self._scale_label.show()
        self._topmost_check.show()
        self._flight_data_check.show()

        # 隐藏简要模式专属控件
        self._compact_restore_btn.hide()
        self._compact_scale_slider.hide()
        self._compact_scale_label.hide()
        self._compact_size_grip.hide()

        # 恢复布局
        self._layout_radar_widget()
        self._layout_side_controls()
        # 确保浮动控件在最上层
        self._opacity_slider.raise_()
        self._scale_slider.raise_()
        self._scale_label.raise_()
        self._topmost_check.raise_()

        self.compactButton.setText("简要")
        self.show()

    def _on_compact_scale_changed(self, value):
        self.scaleComboBox.setCurrentIndex(value)
        # 同步回正常模式滑块
        self._scale_slider.setValue(value)
        self._update_compact_scale_label()
        self._refresh_radar()

    def _update_compact_scale_label(self):
        labels = {0: "50km", 1: "100km", 2: "200km"}
        if config.show_metrics == "nm":
            labels = {0: "25nm", 1: "50nm", 2: "100nm"}
        self._compact_scale_label.setText(
            labels.get(self._compact_scale_slider.value(), "")
        )

    def _layout_compact_controls(self):
        w = self.width()
        h = self.height()
        # 恢复按钮 — 右上角
        self._compact_restore_btn.move(w - 60, 6)
        # 比例尺滑块 — 底部居中
        slider_w = min(200, w - 40)
        self._compact_scale_slider.setFixedWidth(slider_w)
        self._compact_scale_slider.move((w - slider_w) // 2, h - 44)
        self._compact_scale_label.setFixedWidth(slider_w)
        self._compact_scale_label.move((w - slider_w) // 2, h - 24)
        # 尺寸调节手柄 — 右下角
        self._compact_size_grip.move(w - 18, h - 18)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.center_x = self.width() // 2
        self.center_y = self.height() // 2
        if self._compact_mode:
            self.radar_widget.setGeometry(0, 0, self.width(), self.height())
            self._layout_compact_controls()
        else:
            self._layout_radar_widget()
            self._layout_side_controls()
        self._schedule_refresh()

    def _metrics_changed(self, index):
        if index == 0:
            config.show_metrics = "km"
            self.scaleComboBox.clear()
            self.scaleComboBox.addItems(["50km", "100km", "200km"])
        else:
            config.show_metrics = "nm"
            self.scaleComboBox.clear()
            self.scaleComboBox.addItems(["25nm", "50nm", "100nm"])
        self._refresh_radar()

    # =========================================================================
    # 设置对话框
    # =========================================================================

    def _show_settings(self):
        # 防止重复打开设置对话框
        if hasattr(self, '_settings_dialog') and self._settings_dialog is not None:
            if self._settings_dialog.isVisible():
                logger.info("MainWindow: 设置对话框已打开，激活现有窗口")
                self._settings_dialog.raise_()
                self._settings_dialog.activateWindow()
                return

        from ui.settings_dialog import SettingsDialog
        # 使用非模态 show() 而非 exec()，否则对话框 hide() 时会直接退出事件循环，
        # 导致 QTimer.singleShot 回调永远无法执行（AreaSelector 拖拽选取功能失效）。
        self._settings_dialog = SettingsDialog(self)
        self._settings_dialog.finished.connect(self._on_settings_finished)
        self._settings_dialog.show()

    def _on_settings_finished(self, result):
        if result == self._settings_dialog.DialogCode.Accepted:
            self.args_ready = True
            logger.info("MainWindow: 设置已确认, args_ready=True")
        else:
            logger.info("MainWindow: 设置已取消")
        self._settings_dialog = None

    # =========================================================================
    # 任务生命周期（开始/停止合并为单一按钮）
    # =========================================================================

    def _toggle_mission(self):
        """单按钮切换：点击开始 → 任务运行中 → 点击停止。"""
        if self._mission_running:
            self._end_mission()
        else:
            self._start_mission()

    def _start_mission(self):
        self._refresh_radar()

        if not self.args_ready:
            QMessageBox.warning(self, "参数未准备好",
                                "请确保所有参数已准备好后再开始任务。")
            return

        # ---- UDP 监听线程 ----
        if not (self._udp_thread and self._udp_thread.isRunning()):
            self._udp_thread = QThread()
            self._udp_worker = SocketWorker()
            self._udp_worker.moveToThread(self._udp_thread)
            self._udp_worker.data_received.connect(self._on_udp_data)
            self._udp_thread.started.connect(self._udp_worker.start_listening)
            self._udp_thread.start()

        # ---- OCR 工作线程 ----
        if not (self._ocr_thread and self._ocr_thread.isRunning()):
            self._ocr_thread = QThread()
            self._ocr_worker = OCRWorker()
            self._ocr_worker.moveToThread(self._ocr_thread)
            self._ocr_worker.data_received.connect(self._on_ocr_result)
            self._ocr_thread.start()

        # ---- Team 工作线程 ----
        if not (self._team_thread and self._team_thread.isRunning()):
            self._team_thread = QThread()
            self._team_worker = TeamWorker()
            self._team_worker.moveToThread(self._team_thread)
            self._team_worker.data_received.connect(self._on_team_result)
            self._team_thread.start()

        # ---- 定时器 ----
        if config.show_enemy:
            self._timer_ocr.start(TIMER_OCR_MS)
            self._timer_screen.start(TIMER_SCREENSHOT_MS)
        if config.show_friend:
            self._timer_team.start(TIMER_TEAM_MS)

        # ---- 服务器地址 ----
        if config.is_default_server:
            config.server_ip = DEFAULT_SERVER_HOST
            config.server_port = DEFAULT_SERVER_PORT

        # 按钮状态: 开始 → 停止
        self.startButton.setText("停止")
        self.inforButton.setEnabled(False)
        self._mission_running = True

    def _end_mission(self):
        # 停止定时器
        self._timer_ocr.stop()
        self._timer_screen.stop()
        self._timer_team.stop()

        # 停止 UDP 线程
        if self._udp_worker:
            self._udp_worker.stop_listening()
        if self._udp_thread and self._udp_thread.isRunning():
            self._udp_thread.quit()
            self._udp_thread.wait()
            self._udp_thread = None
            self._udp_worker = None

        # 停止 OCR 线程
        if self._ocr_worker:
            self._ocr_worker.stop()
        if self._ocr_thread and self._ocr_thread.isRunning():
            self._ocr_thread.quit()
            self._ocr_thread.wait()
            self._ocr_thread = None
            self._ocr_worker = None

        # 停止 Team 线程
        if self._team_worker:
            self._team_worker.stop()
        if self._team_thread and self._team_thread.isRunning():
            self._team_thread.quit()
            self._team_thread.wait()
            self._team_thread = None
            self._team_worker = None

        self.screen_shot_list.clear()

        # 按钮状态: 停止 → 开始
        self.startButton.setText("开始")
        self.inforButton.setEnabled(True)
        self._mission_running = False
        self._mission_running = False

    # =========================================================================
    # 定时器回调
    # =========================================================================

    def _tick_screenshot(self):
        if len(self.screen_shot_list) >= 2:
            return
        self.screen_shot_list.clear()
        r = config.screenshot_region
        self.screen_shot_list.append(
            take_screenshot(r["x"], r["y"], r["width"], r["height"])
        )

    def _tick_ocr(self):
        if not (self._udp_thread and self._udp_thread.isRunning()):
            logger.debug("_tick_ocr: UDP 线程未运行，跳过")
            return
        if not (self._ocr_thread and self._ocr_thread.isRunning()):
            logger.debug("_tick_ocr: OCR 线程未运行，跳过")
            return
        if not self._ocr_worker:
            logger.debug("_tick_ocr: OCR worker 不存在，跳过")
            return

        shots = list(self.screen_shot_list)
        logger.debug("_tick_ocr: 提交 OCR, screenshots=%d, mode=%s, callsign=%s%s",
                     len(shots), config.server_mode,
                     config.call_sign["text"], config.call_sign["num"])

        self._ocr_worker.configure(
            screenshots=shots,
            call_sign=config.call_sign,
            message_dic=self.message_dic,
            bullseye_dic=self.bullseye_dic,
            plane_data=self.plane_data,
            bullseye=config.bullseye,
        )
        QMetaObject.invokeMethod(self._ocr_worker, "run",
                                 Qt.ConnectionType.QueuedConnection)

    def _tick_team(self):
        if not (self._udp_thread and self._udp_thread.isRunning()):
            return
        if not (self._team_thread and self._team_thread.isRunning()):
            return
        if not self._team_worker:
            return

        self._team_worker.configure(self.plane_data)
        QMetaObject.invokeMethod(self._team_worker, "run",
                                 Qt.ConnectionType.QueuedConnection)

    # =========================================================================
    # 信号处理
    # =========================================================================

    def _on_udp_data(self, message: str):
        try:
            parts = message.split(",")
            if len(parts) < 10:
                return
            data = {
                "heading": float(parts[4]),
                "x": float(parts[1]),
                "y": float(parts[2]),
                "z": float(parts[3]),
                "height": float(parts[9]),
            }
            # 新格式 (14 字段): 包含 pitch(5), alt_bar(10), alt_rad(11),
            #   true_air_speed(12), indicated_air_speed(13)
            if len(parts) >= 14:
                data["pitch"] = float(parts[5])
                data["alt_bar"] = float(parts[10])
                data["alt_rad"] = float(parts[11])
                data["true_air_speed"] = float(parts[12])
                data["indicated_air_speed"] = float(parts[13])
            self.plane_data = data
            self._schedule_refresh()
        except (ValueError, IndexError) as exc:
            logger.warning("UDP 数据解析错误: %s", exc)

    def _on_ocr_result(self, result):
        if result is None:
            logger.debug("_on_ocr_result: result=None, 跳过")
            return
        message_dic, bullseye_dic = result
        logger.info("_on_ocr_result: message_dic=%d 条, bullseye_dic=%d 条",
                     len(message_dic), len(bullseye_dic))
        for key, msg in message_dic.items():
            logger.debug("  msg key=%s times=%d alt=%s x=%.0f z=%.0f heading=%s cond=%s",
                         key, msg.get("times", 0), msg.get("enemy_altitude", "?"),
                         msg.get("x", 0), msg.get("z", 0),
                         msg.get("enemy_heading", "?"), msg.get("condition", "?"))
        self.message_dic = message_dic
        self.bullseye_dic = bullseye_dic
        self._refresh_radar()

    def _on_team_result(self, team_list):
        if team_list is not None:
            self.team_members = team_list
        self._refresh_radar()
