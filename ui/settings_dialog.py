# -*- coding: utf-8 -*-
"""参数输入对话框 — 标签页布局 + 截图区域可视化选取。

标签页:
    基本 — 代号、靶眼坐标、单位、残留时间
    截图 — 可视化区域选取 + 手动微调
    功能 — 敌机/队友显示、小队代码、服务器模式
    服务器 — 地址、端口、连通测试
"""

from PySide6.QtWidgets import (
    QDialog, QTabWidget, QWidget, QVBoxLayout, QHBoxLayout,
    QFormLayout, QGridLayout, QLineEdit, QComboBox, QCheckBox,
    QPushButton, QLabel, QGroupBox, QMessageBox, QFrame,
)
from PySide6.QtCore import Qt, QRect, QTimer
from PySide6.QtGui import QFont

from config import config
from constants import DEFAULT_SERVER_HOST, DEFAULT_SERVER_PORT
from network.http_client import check_server_health
from ui.area_selector import AreaSelector
from log import get_logger

logger = get_logger(__name__)


def _make_readonly(frame: QFrame, text: str = "") -> QLineEdit:
    """创建一个只读样式的输入框（用于展示数值但不允许直接输入）。"""
    le = QLineEdit(text)
    le.setReadOnly(True)
    le.setStyleSheet(
        "QLineEdit { background-color: #1a1a1a; color: #aaa; border: 1px solid #444; }"
    )
    return le


class SettingsDialog(QDialog):
    """参数输入对话框 — 标签页布局，优化人机工效。"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("信息输入")
        self.resize(500, 420)
        self.setMinimumSize(460, 380)

        self._area_selector = None

        # ---- 根布局 ----
        root = QVBoxLayout(self)
        root.setContentsMargins(8, 8, 8, 8)

        # ---- 标签页 ----
        self._tabs = QTabWidget()
        self._tabs.addTab(self._create_basic_tab(), "基本")
        self._tabs.addTab(self._create_screenshot_tab(), "截图")
        self._tabs.addTab(self._create_features_tab(), "功能")
        self._tabs.addTab(self._create_server_tab(), "服务器")
        root.addWidget(self._tabs)

        # ---- 底部按钮 ----
        btn_row = QHBoxLayout()
        btn_row.addStretch()
        self._ok_btn = QPushButton("确认")
        self._ok_btn.setFixedWidth(80)
        self._ok_btn.clicked.connect(self._on_accept)
        self._cancel_btn = QPushButton("取消")
        self._cancel_btn.setFixedWidth(80)
        self._cancel_btn.clicked.connect(self.reject)
        btn_row.addWidget(self._ok_btn)
        btn_row.addWidget(self._cancel_btn)
        root.addLayout(btn_row)

        # ---- 样式 ----
        self.setStyleSheet("""
            QDialog {
                background-color: #1a1a1a;
                color: #cccccc;
            }
            QTabWidget::pane {
                border: 1px solid #333;
                background-color: #1a1a1a;
            }
            QTabBar::tab {
                background-color: #222;
                color: #999;
                border: 1px solid #333;
                padding: 6px 14px;
                margin-right: 1px;
            }
            QTabBar::tab:selected {
                background-color: #2a2a2a;
                color: #00cc77;
                border-bottom: 2px solid #00cc77;
            }
            QTabBar::tab:hover:!selected {
                background-color: #282828;
                color: #ccc;
            }
            QLabel {
                color: #bbb;
            }
            QLineEdit {
                background-color: #252525;
                color: #ddd;
                border: 1px solid #444;
                border-radius: 3px;
                padding: 4px 6px;
            }
            QLineEdit:focus {
                border-color: #00aa66;
            }
            QLineEdit:disabled {
                background-color: #1a1a1a;
                color: #666;
            }
            QComboBox {
                background-color: #252525;
                color: #ddd;
                border: 1px solid #444;
                border-radius: 3px;
                padding: 4px 6px;
            }
            QComboBox:focus {
                border-color: #00aa66;
            }
            QComboBox QAbstractItemView {
                background-color: #252525;
                color: #ddd;
                selection-background-color: #00aa66;
            }
            QCheckBox {
                color: #ccc;
                spacing: 6px;
            }
            QCheckBox::indicator {
                width: 16px;
                height: 16px;
            }
            QPushButton {
                background-color: #2a2a2a;
                color: #ccc;
                border: 1px solid #444;
                border-radius: 3px;
                padding: 5px 14px;
            }
            QPushButton:hover {
                background-color: #3a3a3a;
            }
            QPushButton#selectAreaBtn {
                background-color: #006633;
                color: #00ff88;
                border: 1px solid #00aa55;
                font-weight: bold;
                padding: 8px 20px;
            }
            QPushButton#selectAreaBtn:hover {
                background-color: #008844;
            }
            QGroupBox {
                color: #aaa;
                border: 1px solid #333;
                border-radius: 4px;
                margin-top: 8px;
                padding-top: 12px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 4px;
            }
        """)

        # ---- 从配置填充表单 ----
        self._populate_from_config()

    # =========================================================================
    # 标签页构建
    # =========================================================================

    def _create_basic_tab(self) -> QWidget:
        """基本标签页：代号、靶眼坐标、预警机单位、敌机残留时间。"""
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(10)

        # 代号
        group_cs = QGroupBox("呼号 (Callsign)")
        cs_layout = QVBoxLayout(group_cs)
        self.callSignLineEdit = QLineEdit()
        self.callSignLineEdit.setPlaceholderText("例如: Springfield1")
        self.callSignLineEdit.setToolTip("预警机叫你的呼号，含字母和数字")
        cs_layout.addWidget(self.callSignLineEdit)
        layout.addWidget(group_cs)

        # 靶眼坐标
        group_be = QGroupBox("靶眼坐标 (Bullseye)")
        be_layout = QFormLayout(group_be)
        be_layout.setSpacing(8)
        self.bullsEyeLong = QLineEdit()
        self.bullsEyeLong.setPlaceholderText("X / 经度")
        self.bullsEyeLat = QLineEdit()
        self.bullsEyeLat.setPlaceholderText("Z / 纬度")
        be_layout.addRow("X (经度):", self.bullsEyeLong)
        be_layout.addRow("Z (纬度):", self.bullsEyeLat)
        layout.addWidget(group_be)

        # 单位 & 残留时间
        row = QHBoxLayout()
        row.setSpacing(12)

        unit_gb = QGroupBox("预警机通报单位")
        unit_layout = QVBoxLayout(unit_gb)
        self.AWACASMARK_unit = QComboBox()
        # auto：SPS/BSC 面板自带单位（NM/ft 或 KM/m），无需设置；
        # 传统预警机文本里没有单位，必须二选一，auto 会回退 km。
        self.AWACASMARK_unit.addItems(["auto", "KM", "NM"])
        self.AWACASMARK_unit.setToolTip(
            "auto：SPS/BSC 面板自动识别（推荐）；\n"
            "传统预警机通报没有单位，请直接选 KM 或 NM"
        )
        unit_layout.addWidget(self.AWACASMARK_unit)
        row.addWidget(unit_gb)

        time_gb = QGroupBox("敌机残留时间 (秒)")
        time_layout = QVBoxLayout(time_gb)
        self.RemainTime = QLineEdit()
        self.RemainTime.setPlaceholderText("90")
        self.RemainTime.setToolTip("敌机信息在屏幕上消失的时间（秒）")
        time_layout.addWidget(self.RemainTime)
        row.addWidget(time_gb)

        ttl_gb = QGroupBox("消息保留窗口 (秒)")
        ttl_layout = QVBoxLayout(ttl_gb)
        self.MessageTTL = QLineEdit()
        self.MessageTTL.setPlaceholderText("120")
        self.MessageTTL.setToolTip(
            "只读取最近 N 秒的预警机通报（钩子日志窗口），建议不小于残留时间"
        )
        ttl_layout.addWidget(self.MessageTTL)
        row.addWidget(ttl_gb)

        layout.addLayout(row)
        layout.addStretch()
        return page

    def _create_screenshot_tab(self) -> QWidget:
        """截图标签页：区域选取按钮 + 手动微调坐标。"""
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(10)

        # ———— 选取按钮 ————
        self._select_area_btn = QPushButton("🎯 拖拽选取截图区域")
        self._select_area_btn.setObjectName("selectAreaBtn")
        self._select_area_btn.setFixedHeight(40)
        self._select_area_btn.setToolTip(
            "隐藏对话框，在屏幕上拖拽框选要截取的敌机信息区域"
        )
        self._select_area_btn.clicked.connect(self._start_area_selection)
        layout.addWidget(self._select_area_btn)

        # ———— 坐标输入 ————
        coords_gb = QGroupBox("截图区域坐标（可手动微调）")
        grid = QGridLayout(coords_gb)
        grid.setSpacing(6)

        self.xEdit = QLineEdit()
        self.xEdit.setPlaceholderText("左边界 X")
        self.yEdit = QLineEdit()
        self.yEdit.setPlaceholderText("上边界 Y")
        self.widthEdit = QLineEdit()
        self.widthEdit.setPlaceholderText("宽度")
        self.heightEdit = QLineEdit()
        self.heightEdit.setPlaceholderText("高度")

        labels = [
            ("X (左边界):", self.xEdit, 0, 0),
            ("Y (上边界):", self.yEdit, 0, 1),
            ("宽度:", self.widthEdit, 1, 0),
            ("高度:", self.heightEdit, 1, 1),
        ]
        for label_text, widget, row, col in labels:
            lbl = QLabel(label_text)
            lbl.setFixedWidth(80)
            grid.addWidget(lbl, row, col * 2)
            grid.addWidget(widget, row, col * 2 + 1)

        layout.addWidget(coords_gb)

        # ———— 提示 ————
        hint = QLabel(
            "提示：点击「拖拽选取截图区域」按钮后，用鼠标在屏幕上框选"
            "敌机信息所在的区域，松开后自动填入坐标。\n"
            "如果 OCR 无法识别正确内容，请确保截图区域恰好包围文字。"
        )
        hint.setWordWrap(True)
        hint.setStyleSheet("color: #777; font-size: 11px; padding: 4px;")
        layout.addWidget(hint)

        layout.addStretch()
        return page

    def _create_features_tab(self) -> QWidget:
        """功能标签页：开关、小队代码、服务器模式。"""
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(10)

        # 开关
        sw_gb = QGroupBox("显示选项")
        sw_layout = QVBoxLayout(sw_gb)
        self.showEnemyCheckBox = QCheckBox("显示敌机（需截图 + OCR）")
        self.showFriendCheckBox = QCheckBox("显示队友（需小队代码匹配）")
        self.showEnemyCheckBox.stateChanged.connect(self._on_show_enemy_changed)
        self.showFriendCheckBox.stateChanged.connect(self._on_show_friend_changed)
        sw_layout.addWidget(self.showEnemyCheckBox)
        sw_layout.addWidget(self.showFriendCheckBox)
        layout.addWidget(sw_gb)

        # 小队代码
        team_gb = QGroupBox("小队识别")
        team_layout = QFormLayout(team_gb)
        self.teamCodeEdit = QLineEdit()
        self.teamCodeEdit.setPlaceholderText("例如: 9214")
        self.teamCodeEdit.setToolTip("和其他人代码一样，会显示对应小队")
        team_layout.addRow("小队代码:", self.teamCodeEdit)
        layout.addWidget(team_gb)

        # 服务器模式
        mode_gb = QGroupBox("服务器模式")
        mode_layout = QFormLayout(mode_gb)
        self.serverMode = QComboBox()
        self.serverMode.addItems(["传统预警机", "传统预警机(英文)", "SPS服务器", "BSC服务器"])
        self.serverMode.setToolTip(
            "传统预警机=左上角BRA通报 | SPS=右侧面板报点 | BSC=右侧面板"
        )
        mode_layout.addRow("模式:", self.serverMode)
        layout.addWidget(mode_gb)

        layout.addStretch()
        return page

    def _create_server_tab(self) -> QWidget:
        """服务器标签页：地址、端口、连通测试。"""
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(10)

        # 默认服务器开关
        self.serverCheckBox = QCheckBox("使用默认服务器")
        self.serverCheckBox.stateChanged.connect(self._on_server_check_changed)
        layout.addWidget(self.serverCheckBox)

        # 服务器信息
        svr_gb = QGroupBox("服务器连接")
        svr_layout = QFormLayout(svr_gb)
        svr_layout.setSpacing(8)

        self.serverHostEdit = QLineEdit()
        self.serverHostEdit.setPlaceholderText(DEFAULT_SERVER_HOST)
        self.portEdit = QLineEdit()
        self.portEdit.setPlaceholderText(str(DEFAULT_SERVER_PORT))

        svr_layout.addRow("地址:", self.serverHostEdit)
        svr_layout.addRow("端口:", self.portEdit)

        # 测试按钮 + 结果
        test_row = QHBoxLayout()
        self.testButton = QPushButton("服务器连通测试")
        self.testButton.clicked.connect(self._test_connection)
        test_row.addWidget(self.testButton)
        test_row.addStretch()
        svr_layout.addRow("", test_row)

        self.logShow = QLabel("")
        self.logShow.setStyleSheet("color: #888; padding: 4px;")
        svr_layout.addRow("", self.logShow)

        layout.addWidget(svr_gb)
        layout.addStretch()
        return page

    # =========================================================================
    # 截图区域选取
    # =========================================================================

    def _start_area_selection(self):
        """隐藏对话框，显示全屏区域选择器。"""
        logger.info("SettingsDialog: 用户点击「拖拽选取截图区域」")
        self.hide()
        logger.debug("SettingsDialog: 对话框已隐藏, isVisible=%s", self.isVisible())
        # 短暂延迟确保对话框完全隐藏后再显示选择器
        QTimer.singleShot(200, self._show_selector)

    def _show_selector(self):
        logger.debug("SettingsDialog._show_selector: 开始创建 AreaSelector")
        try:
            self._area_selector = AreaSelector()
        except Exception as exc:
            logger.error("SettingsDialog: AreaSelector 创建失败: %s", exc, exc_info=True)
            # 创建失败则恢复对话框并提示错误
            self.show()
            self.raise_()
            self.activateWindow()
            QMessageBox.warning(self, "截图选取失败",
                              f"无法启动区域选择器：{exc}\n\n"
                              "请在「截图」标签页中手动输入坐标。")
            return
        self._area_selector.area_selected.connect(self._on_area_selected)
        self._area_selector.selection_cancelled.connect(self._on_selection_cancelled)
        self._area_selector.show()
        logger.debug("SettingsDialog: AreaSelector.show() 已调用")

    def _on_area_selected(self, rect: QRect):
        """区域选取完成 → 回填坐标。"""
        logger.info("SettingsDialog: 选区完成 rect=(%d,%d %dx%d)",
                     rect.x(), rect.y(), rect.width(), rect.height())
        self.xEdit.setText(str(rect.x()))
        self.yEdit.setText(str(rect.y()))
        self.widthEdit.setText(str(rect.width()))
        self.heightEdit.setText(str(rect.height()))
        self._area_selector = None
        self.show()
        self.raise_()
        self.activateWindow()

    def _on_selection_cancelled(self):
        """用户取消选取。"""
        logger.info("SettingsDialog: 用户取消了选区")
        self._area_selector = None
        self.show()
        self.raise_()
        self.activateWindow()

    # =========================================================================
    # 从配置填充
    # =========================================================================

    def _populate_from_config(self):
        """从 AppConfig 读取当前值填充表单。"""
        # 基本 — 呼号
        self.callSignLineEdit.setText(
            config.call_sign["text"] + config.call_sign["num"]
        )

        # 基本 — 靶眼
        self.bullsEyeLat.setText(str(config.bullseye["z"]))
        self.bullsEyeLong.setText(str(config.bullseye["x"]))

        # 基本 — 单位 & 残留时间
        _unit = (config.awacs_metric_unit or "auto").lower()
        self.AWACASMARK_unit.setCurrentText({"km": "KM", "nm": "NM"}.get(_unit, "auto"))
        self.RemainTime.setText(str(config.remaining_time))
        self.MessageTTL.setText(str(config.message_ttl))

        # 截图 — 区域
        self.xEdit.setText(str(config.screenshot_region["x"]))
        self.yEdit.setText(str(config.screenshot_region["y"]))
        self.widthEdit.setText(str(config.screenshot_region["width"]))
        self.heightEdit.setText(str(config.screenshot_region["height"]))

        # 功能 — 开关
        self.showEnemyCheckBox.setChecked(config.show_enemy)
        self.showFriendCheckBox.setChecked(config.show_friend)

        # 功能 — 小队代码 & 模式
        self.teamCodeEdit.setText(config.team_code)
        self.serverMode.setCurrentIndex(config.server_mode)

        # 服务器
        self.serverCheckBox.setChecked(config.is_default_server)
        self.serverHostEdit.setText(config.server_ip)
        self.portEdit.setText(str(config.server_port))

        # 联动
        self._on_show_enemy_changed()
        self._on_show_friend_changed()
        self._on_server_check_changed()

    # =========================================================================
    # 复选框联动
    # =========================================================================

    def _on_show_enemy_changed(self):
        enabled = self.showEnemyCheckBox.isChecked()
        self.xEdit.setEnabled(enabled)
        self.yEdit.setEnabled(enabled)
        self.widthEdit.setEnabled(enabled)
        self.heightEdit.setEnabled(enabled)
        self._select_area_btn.setEnabled(enabled)

    def _on_show_friend_changed(self):
        enabled = self.showFriendCheckBox.isChecked()
        self.teamCodeEdit.setEnabled(enabled)

    def _on_server_check_changed(self):
        use_default = self.serverCheckBox.isChecked()
        self.serverHostEdit.setEnabled(not use_default)
        self.portEdit.setEnabled(not use_default)

    # =========================================================================
    # 连接测试
    # =========================================================================

    def _test_connection(self):
        self.logShow.setText("正在测试连接...")
        self.logShow.setStyleSheet("color: #ffcc00; padding: 4px;")
        if self.serverCheckBox.isChecked():
            host = DEFAULT_SERVER_HOST
            port = DEFAULT_SERVER_PORT
        else:
            host = self.serverHostEdit.text().strip()
            try:
                port = int(self.portEdit.text().strip())
            except ValueError:
                self.logShow.setText("⚠ 端口号格式错误！")
                self.logShow.setStyleSheet("color: #ff4444; padding: 4px;")
                return

        reachable = check_server_health(host, port)
        if reachable:
            self.logShow.setText("✓ 连接测试成功！")
            self.logShow.setStyleSheet("color: #00cc77; padding: 4px;")
        else:
            self.logShow.setText("✗ 连接测试失败")
            self.logShow.setStyleSheet("color: #ff4444; padding: 4px;")

    # =========================================================================
    # 确认保存
    # =========================================================================

    def _on_accept(self):
        """确认按钮：验证输入并写回配置。"""
        call_sign_text = self.callSignLineEdit.text().strip()
        if not call_sign_text or call_sign_text == "abc9527":
            QMessageBox.warning(self, "输入错误", "请至少输入代号 (Callsign)。")
            return

        try:
            # 呼号
            config.call_sign["text"] = "".join(filter(str.isalpha, call_sign_text))
            config.call_sign["num"] = "".join(filter(str.isdigit, call_sign_text))

            # 靶眼坐标
            config.bullseye["z"] = float(self.bullsEyeLat.text().strip() or "0")
            config.bullseye["x"] = float(self.bullsEyeLong.text().strip() or "0")

            # 截图区域
            config.screenshot_region["x"] = int(self.xEdit.text() or "0")
            config.screenshot_region["y"] = int(self.yEdit.text() or "0")
            config.screenshot_region["width"] = int(self.widthEdit.text() or "600")
            config.screenshot_region["height"] = int(self.heightEdit.text() or "400")

            # 单位 & 模式
            _unit_text = self.AWACASMARK_unit.currentText()
            config.awacs_metric_unit = {"KM": "km", "NM": "nm"}.get(_unit_text, "auto")
            config.remaining_time = int(self.RemainTime.text().strip() or "90")
            config.message_ttl = max(10, int(self.MessageTTL.text().strip() or "120"))
            config.server_mode = self.serverMode.currentIndex()

            # 小队
            config.team_code = self.teamCodeEdit.text().strip()

            # 服务器
            config.server_ip = self.serverHostEdit.text().strip()
            config.server_port = int(self.portEdit.text().strip() or str(DEFAULT_SERVER_PORT))

        except ValueError as exc:
            QMessageBox.warning(self, "输入错误", f"数值格式错误: {exc}")
            return

        # 功能开关
        config.show_enemy = self.showEnemyCheckBox.isChecked()
        config.show_friend = self.showFriendCheckBox.isChecked()
        config.is_default_server = self.serverCheckBox.isChecked()

        # 持久化
        config.save_to_disk()
        self.accept()
