# -*- coding: utf-8 -*-
"""屏幕区域选择器 — 全屏截图打底 + 半透明遮罩，鼠标拖拽框选区域。

采用"截图底板"方案替代透明窗口挖洞：先截取全屏作为背景，再覆盖
半透明暗色遮罩，选中区域内显示无遮罩的原始截图。比透明窗口方案
更可靠（尤其在 Windows 上）。
"""

from PySide6.QtWidgets import QWidget, QApplication
from PySide6.QtCore import Qt, QRect, Signal
from PySide6.QtGui import (
    QPainter, QPen, QColor, QFont, QPixmap, QScreen,
)

from log import get_logger

logger = get_logger(__name__)


class AreaSelector(QWidget):
    """全屏区域选择器。

    Usage:
        selector = AreaSelector()
        selector.area_selected.connect(on_area_selected)
        selector.show()
    """

    area_selected = Signal(QRect)
    selection_cancelled = Signal()

    def __init__(self):
        super().__init__()

        logger.debug("AreaSelector.__init__ 开始")

        # 纯无边框 + 置顶 + 显式顶层窗口，不加 Tool（Windows 上 Tool 会导致收不到鼠标事件）
        self.setWindowFlags(
            Qt.WindowType.Window
            | Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
        )
        # 不透明背景（我们用截图做底）
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, False)
        # 确保窗口能接收鼠标事件（Windows 上尤其重要）
        self.setAttribute(Qt.WidgetAttribute.WA_Hover, True)

        # 打印屏幕信息以便排查 DPI / 多屏问题
        for i, s in enumerate(QApplication.screens()):
            geo = s.geometry()
            logger.debug(
                "屏幕[%d]: geometry=(%d,%d %dx%d) dpi=%.1f devicePixelRatio=%.1f",
                i, geo.x(), geo.y(), geo.width(), geo.height(),
                s.logicalDotsPerInch(), s.devicePixelRatio(),
            )

        # 截取全屏作为底板（必须在 show 之前完成）
        logger.debug("AreaSelector: 开始全屏截图...")
        self._screen_bg = self._grab_all_screens()
        logger.debug("AreaSelector: 全屏截图完成, size=%dx%d",
                     self._screen_bg.width(), self._screen_bg.height())

        # 覆盖所有屏幕
        self._total_rect = self._calc_total_screen_rect()
        logger.debug("AreaSelector: 虚拟桌面区域=(%d,%d %dx%d)",
                     self._total_rect.x(), self._total_rect.y(),
                     self._total_rect.width(), self._total_rect.height())
        self.setGeometry(self._total_rect)
        logger.debug("AreaSelector: 窗口几何已设置为 %s", self.geometry())

        # ---- 内部状态 ----
        self._start = None
        self._current = None
        self._selecting = False
        self._paint_count = 0     # 绘制计数器，用于排查 paintEvent 是否触发

        # ---- 颜色 ----
        self._overlay = QColor(0, 0, 0, 130)       # 半透明黑遮罩
        self._border = QColor(0, 230, 140)           # 选框边框
        self._fill = QColor(0, 230, 140, 35)         # 选框淡绿填充
        self._label_bg = QColor(0, 0, 0, 180)        # 标签背景
        self._label_fg = QColor(220, 255, 220)       # 标签文字

        self.setCursor(Qt.CursorShape.CrossCursor)
        self.setMouseTracking(True)
        # 确保能收到键盘和鼠标事件
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)

        logger.info("AreaSelector.__init__ 完成")

    # -----------------------------------------------------------------
    # 全屏截图
    # -----------------------------------------------------------------

    @staticmethod
    def _grab_all_screens() -> QPixmap:
        """截取所有屏幕并拼接为一张大图。"""
        screens = QApplication.screens()
        if not screens:
            logger.warning("AreaSelector: 未检测到任何屏幕，使用默认 1920x1080")
            return QPixmap(1920, 1080)

        total = AreaSelector._calc_total_screen_rect()
        result = QPixmap(total.width(), total.height())
        result.fill(Qt.GlobalColor.black)

        painter = QPainter(result)
        for s in screens:
            geo = s.geometry()
            offset_x = geo.x() - total.x()
            offset_y = geo.y() - total.y()
            logger.debug("AreaSelector: 截屏 screen geo=%s, offset=(%d,%d)",
                         geo, offset_x, offset_y)
            # grabWindow(0) 是相对该屏幕自身的坐标，不是虚拟桌面坐标
            pix = s.grabWindow(0)
            logger.debug("AreaSelector: 截屏像素 size=%dx%d",
                         pix.width(), pix.height())
            painter.drawPixmap(offset_x, offset_y, pix)
        painter.end()
        logger.debug("AreaSelector: 全屏拼接完成, result=%dx%d",
                     result.width(), result.height())
        return result

    # -----------------------------------------------------------------
    # 多屏矩形
    # -----------------------------------------------------------------

    @staticmethod
    def _calc_total_screen_rect() -> QRect:
        screens = QApplication.screens()
        if not screens:
            return QRect(0, 0, 1920, 1080)
        rect = screens[0].geometry()
        for s in screens[1:]:
            rect = rect.united(s.geometry())
        return rect

    @staticmethod
    def _get_device_pixel_ratio() -> float:
        """获取主屏幕的 devicePixelRatio，用于逻辑坐标→物理像素转换。

        Qt 工作在逻辑坐标空间（受 Windows 缩放影响），但 mss 截图库
        使用物理像素。例如 150% 缩放时 DPR=1.5，逻辑 2560 → 物理 3840。
        """
        screens = QApplication.screens()
        if not screens:
            return 1.0
        # 使用主屏幕的 DPR；多屏不同 DPI 场景极为罕见
        return screens[0].devicePixelRatio()

    # -----------------------------------------------------------------
    # 绘制
    # -----------------------------------------------------------------

    def paintEvent(self, event):
        self._paint_count += 1
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        w, h = self.width(), self.height()

        # 背景截图有效性检查
        if self._screen_bg.isNull():
            logger.error("AreaSelector: _screen_bg 为空，无法绘制背景！")
            painter.fillRect(self.rect(), QColor(30, 30, 30))
            font = QFont()
            font.setPointSize(14)
            painter.setFont(font)
            painter.setPen(QColor(255, 80, 80))
            painter.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter,
                             "截图失败，请按 Esc 退出后重试")
            painter.end()
            return

        if self._start is not None and self._current is not None:
            sel = QRect(self._start, self._current).normalized()
            # DPI 缩放：显示标签用物理像素值，与 mss 截图坐标一致
            dpr = self._get_device_pixel_ratio()

            # 选区外：截图 + 暗色遮罩
            # 上条
            if sel.top() > 0:
                src = self._screen_bg.copy(0, 0, w, sel.top())
                painter.drawPixmap(0, 0, src)
                painter.fillRect(0, 0, w, sel.top(), self._overlay)
            # 下条
            if sel.bottom() < h:
                y = sel.bottom()
                src = self._screen_bg.copy(0, y, w, h - y)
                painter.drawPixmap(0, y, src)
                painter.fillRect(0, y, w, h - y, self._overlay)
            # 左条
            if sel.left() > 0:
                y = max(0, sel.top())
                strip_h = min(h, sel.bottom()) - y
                src = self._screen_bg.copy(0, y, sel.left(), strip_h)
                painter.drawPixmap(0, y, src)
                painter.fillRect(0, y, sel.left(), strip_h, self._overlay)
            # 右条
            if sel.right() < w:
                y = max(0, sel.top())
                strip_h = min(h, sel.bottom()) - y
                x = sel.right()
                src = self._screen_bg.copy(x, y, w - x, strip_h)
                painter.drawPixmap(x, y, src)
                painter.fillRect(x, y, w - x, strip_h, self._overlay)

            # 选区内：截图（无遮罩，保持原始亮度）
            sel_src = self._screen_bg.copy(sel)
            painter.drawPixmap(sel.topLeft(), sel_src)

            # 选区边框
            pen = QPen(self._border, 2, Qt.PenStyle.SolidLine)
            painter.setPen(pen)
            painter.setBrush(self._fill)
            painter.drawRect(sel)

            # ---- 尺寸标签（物理像素） ----
            pw = int(round(sel.width() * dpr))
            ph = int(round(sel.height() * dpr))
            self._draw_label(painter, sel, f"{pw} × {ph}",
                             sel.center().x(), sel.top() - 22,
                             sel.top() < 30, sel.bottom() + 4)

            # ---- 坐标标签（物理像素，左上角全局坐标） ----
            top_left = self.mapToGlobal(sel.topLeft())
            px = int(round(top_left.x() * dpr))
            py = int(round(top_left.y() * dpr))
            coord = f"({px}, {py})"
            self._draw_label(painter, sel, coord,
                             sel.left() + 4, sel.top() + 4,
                             False, None)

        else:
            # 无选区：全屏截图 + 暗色遮罩 + 提示文字
            painter.drawPixmap(0, 0, self._screen_bg)
            painter.fillRect(self.rect(), self._overlay)

            font = QFont()
            font.setPointSize(16)
            painter.setFont(font)
            painter.setPen(self._label_fg)

            hint = "拖拽鼠标框选截图区域（坐标均为物理像素） — 按 Esc 取消"
            fm = painter.fontMetrics()
            text_w = fm.horizontalAdvance(hint)
            text_h = fm.height()
            tx = (w - text_w) // 2
            ty = (h - text_h) // 2

            # 半透明背景
            painter.fillRect(tx - 16, ty - 8, text_w + 32, text_h + 20,
                             QColor(0, 0, 0, 160))
            painter.drawText(tx, ty + text_h - 4, hint)

        painter.end()

    def _draw_label(self, painter, sel, text, cx, default_y, flip, alt_y):
        """在选框边缘绘制标签，超出屏幕则翻转到选框内侧。"""
        font = QFont()
        font.setPointSize(11)
        font.setBold(True)
        painter.setFont(font)
        painter.setPen(self._label_fg)

        fm = painter.fontMetrics()
        tw = fm.horizontalAdvance(text)
        th = fm.height()

        lx = cx - tw // 2
        ly = default_y
        if flip and default_y < th + 4:
            ly = alt_y

        painter.fillRect(lx - 4, ly - 2, tw + 8, th + 6, self._label_bg)
        painter.drawText(lx, ly + th - 3, text)

    # -----------------------------------------------------------------
    # 鼠标事件
    # -----------------------------------------------------------------

    def mousePressEvent(self, event):
        pos = event.position().toPoint()
        logger.debug("AreaSelector.mousePressEvent: button=%s pos=(%d,%d) selecting=%s",
                     event.button().name, pos.x(), pos.y(), self._selecting)
        if event.button() == Qt.MouseButton.LeftButton:
            self._start = pos
            self._current = self._start
            self._selecting = True
            logger.debug("AreaSelector: 开始拖拽选区 start=(%d,%d)", pos.x(), pos.y())
            self.update()
        elif event.button() == Qt.MouseButton.RightButton:
            logger.info("AreaSelector: 右键取消")
            self.selection_cancelled.emit()
            self.close()

    def mouseMoveEvent(self, event):
        if self._selecting:
            self._current = event.position().toPoint()
            self.update()

    def mouseReleaseEvent(self, event):
        pos = event.position().toPoint()
        logger.debug("AreaSelector.mouseReleaseEvent: button=%s pos=(%d,%d) selecting=%s",
                     event.button().name, pos.x(), pos.y(), self._selecting)
        if event.button() == Qt.MouseButton.LeftButton and self._selecting:
            self._current = pos
            self._selecting = False

            sel = QRect(self._start, self._current).normalized()
            if sel.width() >= 10 and sel.height() >= 10:
                # 转为全局屏幕坐标：窗口内的点 + 窗口的全局偏移
                top_left = self.mapToGlobal(sel.topLeft())

                # ---- DPI 缩放转换 ----
                # Qt 工作在逻辑坐标 (如 150% 缩放: 2560)，但 mss 截图库使用
                # 物理像素 (3840)。需要乘以 devicePixelRatio 转换。
                dpr = self._get_device_pixel_ratio()
                global_rect = QRect(
                    int(round(top_left.x() * dpr)),
                    int(round(top_left.y() * dpr)),
                    int(round(sel.width() * dpr)),
                    int(round(sel.height() * dpr)),
                )
                logger.info("AreaSelector: 选区完成 logical=(%d,%d %dx%d) → physical=(%d,%d %dx%d) dpr=%.2f",
                             top_left.x(), top_left.y(),
                             sel.width(), sel.height(),
                             global_rect.x(), global_rect.y(),
                             global_rect.width(), global_rect.height(),
                             dpr)
                self.area_selected.emit(global_rect)
            else:
                logger.info("AreaSelector: 选区太小 (%dx%d)，视为取消",
                             sel.width(), sel.height())
                self.selection_cancelled.emit()
            self.close()

    # -----------------------------------------------------------------
    # 键盘
    # -----------------------------------------------------------------

    def keyPressEvent(self, event):
        logger.debug("AreaSelector.keyPressEvent: key=%s", event.key().name)
        if event.key() == Qt.Key.Key_Escape:
            logger.info("AreaSelector: Esc 取消选区")
            self.selection_cancelled.emit()
            self.close()

    # -----------------------------------------------------------------
    # 显示 / 关闭 — 确保窗口能获得输入焦点
    # -----------------------------------------------------------------

    def showEvent(self, event):
        super().showEvent(event)
        actual_geo = self.geometry()
        logger.debug("AreaSelector.showEvent: isVisible=%s geometry=%s",
                     self.isVisible(), actual_geo)
        # 验证窗口几何是否与预期一致
        if actual_geo != self._total_rect:
            logger.warning("AreaSelector: 窗口几何与预期不一致！预期=%s, 实际=%s",
                           self._total_rect, actual_geo)
        # 强制提升到最前并获取焦点
        self.raise_()
        self.activateWindow()
        self.setFocus()

    def changeEvent(self, event):
        """监听窗口状态变化（激活/失活），用于排查焦点问题。"""
        from PySide6.QtCore import QEvent
        if event.type() == QEvent.Type.ActivationChange:
            logger.debug("AreaSelector: 激活状态变化 isActiveWindow=%s hasFocus=%s",
                         self.isActiveWindow(), self.hasFocus())
        elif event.type() == QEvent.Type.WindowStateChange:
            logger.debug("AreaSelector: 窗口状态变化 windowState=%s",
                         self.windowState())
        super().changeEvent(event)

    def closeEvent(self, event):
        logger.debug("AreaSelector.closeEvent: 窗口关闭, paint_count=%d", self._paint_count)
        super().closeEvent(event)
