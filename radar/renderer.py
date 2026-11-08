# -*- coding: utf-8 -*-
"""雷达渲染器 — 组合网格绘制 + 飞机标记绘制，提供统一的 paint() 入口。

将 main.py 中 3 个 paint 方法 (~650 行重复代码) 整合为一个参数化的渲染函数。
"""

import math
import time
from PySide6.QtGui import QPainter

from constants import (
    NUM_CIRCLES, ANGLE_STEP,
    DISPLAY_MODE_NGAS, DISPLAY_MODE_SA, DISPLAY_MODE_CENTER_SA,
    TIME_ELAPSE_DIVISOR, TIME_ELAPSE_MAX_LEVEL,
    ALTITUDE_LABEL_COLOR,
    M_TO_FT, MPS_TO_KMH, MPS_TO_KTS,
)
from config import config
from radar.grid import draw_radar_grid, draw_aircraft_arrow, draw_altitude_label
from radar.aircraft import draw_enemy_plane, draw_friend_plane
from utils import calculate_bearing_and_distance
from dcs.parser import convert_altitude, convert_distance


def _data_metric(msg: dict) -> str:
    """每条消息自己的原始单位；缺省回退全局配置（老数据兼容）。"""
    metric = msg.get("data_metric") or config.awacs_metric_unit
    return metric if metric in ("km", "nm") else "km"


class RadarRenderer:
    """雷达渲染器 — 无状态，纯绘制逻辑。"""

    # 地图: 模式 → (heading_up, center_y_factor)
    # center_y_factor: 1.0 = 居中, 5/3 ≈ 1.667 = 底部 (y=5/6 → 10/6)
    _MODE_CONFIG = {
        DISPLAY_MODE_NGAS:      {"heading_up": False, "center_y_factor": 1.0},
        DISPLAY_MODE_SA:        {"heading_up": True,  "center_y_factor": 10.0 / 6.0},
        DISPLAY_MODE_CENTER_SA: {"heading_up": True,  "center_y_factor": 1.0},
    }

    def render(self, painter: QPainter, mode: int,
               plane_data: dict, message_dic: dict, bullseye_dic: dict,
               team_members: list, width: int, height: int,
               scale_index: int = 0, display_metric: str = "km"):
        """统一的绘制入口。

        Args:
            painter: QPainter 实例
            mode: 显示模式 (DISPLAY_MODE_NGAS / SA / CENTER_SA)
            plane_data: 本机数据 {heading, x, y, z, height}
            message_dic: 敌机消息字典
            bullseye_dic: 牛眼敌机字典
            team_members: 友机列表
            width, height: 窗口尺寸
            scale_index: 比例尺下拉索引 (0/1/2)
            display_metric: 显示单位 "km" 或 "nm"
        """
        mode_cfg = self._MODE_CONFIG.get(mode, self._MODE_CONFIG[DISPLAY_MODE_NGAS])
        heading_up = mode_cfg["heading_up"]
        center_y_factor = mode_cfg["center_y_factor"]

        # 比例尺: (2**scale_index) * 基数
        base = 50 if display_metric == "km" else 25
        scale = (2 ** scale_index) * base

        # 中心点
        center_x = width / 2
        center_y = height / 2 * center_y_factor

        # 间距
        if mode == DISPLAY_MODE_NGAS:
            radius_interval = min(width, height) // (2 * NUM_CIRCLES + 1)
        else:
            radius_interval = width // (2 * NUM_CIRCLES + 1)

        max_radius = NUM_CIRCLES * radius_interval

        # 航向偏移
        heading_offset = plane_data["heading"] if heading_up else 0.0

        # ---- 1. 网格 ----
        draw_radar_grid(painter, center_x, center_y, NUM_CIRCLES,
                        radius_interval, max_radius, heading_offset)

        # ---- 2. 本机标记 ----
        # 高度标签
        font_size = 8 if mode == DISPLAY_MODE_CENTER_SA else 5
        self._draw_height_label(painter, center_x, center_y, plane_data["y"],
                                display_metric, font_size, mode)

        # 航向箭头
        if heading_up:
            draw_aircraft_arrow(painter, center_x, center_y, 0, radius_interval)
        else:
            draw_aircraft_arrow(painter, center_x, center_y,
                                plane_data["heading"], radius_interval)

        # ---- 3. 友机 ----
        if config.show_friend:
            self._draw_friends(painter, center_x, center_y, plane_data,
                               team_members, scale, radius_interval,
                               max_radius, heading_offset)

        # ---- 4. 敌机 (BRA + 牛眼) ----
        self._draw_enemies(painter, center_x, center_y, plane_data,
                           message_dic, scale, radius_interval,
                           max_radius, heading_offset, display_metric)

        self._draw_bullseyes(painter, center_x, center_y, plane_data,
                             bullseye_dic, scale, radius_interval,
                             max_radius, heading_offset, display_metric)

    # =========================================================================
    # 飞行数据面板
    # =========================================================================

    def render_data_panel(self, painter: QPainter, plane_data: dict,
                          width: int, height: int, display_metric: str = "km"):
        """绘制飞行数据面板，显示本机关键飞行参数。

        Args:
            painter: QPainter 实例
            plane_data: 本机数据 (含 alt_bar, alt_rad, pitch, true_air_speed, indicated_air_speed)
            width, height: 控件尺寸
            display_metric: "km"=公制 / "nm"=英制
        """
        from PySide6.QtGui import QFont, QColor
        from PySide6.QtCore import Qt as QtCore

        painter.setRenderHint(QPainter.Antialiasing)

        is_metric = (display_metric == "km")

        # 单位转换
        if is_metric:
            alt_bar = plane_data.get("alt_bar", 0)          # 米
            alt_rad = plane_data.get("alt_rad", 0)          # 米
            tas = plane_data.get("true_air_speed", 0) * MPS_TO_KMH    # m/s → km/h
            ias = plane_data.get("indicated_air_speed", 0) * MPS_TO_KMH
            alt_unit = "m"
            spd_unit = "km/h"
        else:
            alt_bar = plane_data.get("alt_bar", 0) * M_TO_FT   # 米 → 英尺
            alt_rad = plane_data.get("alt_rad", 0) * M_TO_FT
            tas = plane_data.get("true_air_speed", 0) * MPS_TO_KTS  # m/s → 节
            ias = plane_data.get("indicated_air_speed", 0) * MPS_TO_KTS
            alt_unit = "ft"
            spd_unit = "kts"

        pitch = plane_data.get("pitch", 0)  # 度，公/英制相同

        # 标签与值
        rows = [
            ("海拔高度", f"{alt_bar:.0f} {alt_unit}"),
            ("雷达高度", f"{alt_rad:.0f} {alt_unit}"),
            ("俯仰",     f"{pitch:.1f}°"),
            ("真空速",   f"{tas:.0f} {spd_unit}"),
            ("指示空速", f"{ias:.0f} {spd_unit}"),
        ]

        # 面板尺寸与位置（居中）
        panel_w = min(300, width - 40)
        row_h = 32
        title_h = 36
        padding_v = 16
        panel_h = title_h + len(rows) * row_h + padding_v * 2
        panel_x = (width - panel_w) // 2
        panel_y = (height - panel_h) // 2

        # ---- 面板背景 ----
        painter.setBrush(QColor(8, 16, 8, 210))
        painter.setPen(QColor(60, 140, 60, 180))
        painter.drawRoundedRect(int(panel_x), int(panel_y),
                               int(panel_w), int(panel_h), 8, 8)

        # ---- 标题 ----
        title_font = QFont()
        title_font.setPointSize(13)
        title_font.setBold(True)
        painter.setFont(title_font)
        painter.setPen(QColor(180, 255, 180))
        painter.drawText(
            int(panel_x), int(panel_y + 8),
            int(panel_w), int(title_h),
            QtCore.AlignmentFlag.AlignHCenter | QtCore.AlignmentFlag.AlignVCenter,
            "飞行数据",
        )

        # ---- 分隔线 ----
        line_y = panel_y + title_h + 4
        painter.setPen(QColor(60, 140, 60, 120))
        painter.drawLine(
            int(panel_x + 20), int(line_y),
            int(panel_x + panel_w - 20), int(line_y),
        )

        # ---- 数据行 ----
        label_font = QFont()
        label_font.setPointSize(10)
        painter.setFont(label_font)

        for i, (label, value) in enumerate(rows):
            ry = panel_y + title_h + padding_v + i * row_h

            # 标签 (左侧, 浅灰绿)
            painter.setPen(QColor(140, 200, 140))
            painter.drawText(
                int(panel_x + 24), int(ry),
                int(panel_w * 0.42), int(row_h),
                QtCore.AlignmentFlag.AlignLeft | QtCore.AlignmentFlag.AlignVCenter,
                label,
            )

            # 值 (右侧, 亮白绿)
            val_font = QFont()
            val_font.setPointSize(11)
            val_font.setBold(True)
            painter.setFont(val_font)
            painter.setPen(QColor(220, 255, 220))
            painter.drawText(
                int(panel_x + panel_w * 0.44), int(ry),
                int(panel_w * 0.52 - 24), int(row_h),
                QtCore.AlignmentFlag.AlignRight | QtCore.AlignmentFlag.AlignVCenter,
                value,
            )
            painter.setFont(label_font)  # 恢复为标签字体

    # =========================================================================
    # 内部辅助
    # =========================================================================

    def _draw_height_label(self, painter, cx, cy, altitude_m, metric, font_size, mode):
        from PySide6.QtGui import QFont
        font = QFont()
        font.setPointSize(font_size)
        font.setBold(True)
        painter.setFont(font)
        painter.setPen(ALTITUDE_LABEL_COLOR)

        if metric == "nm":
            h = altitude_m / 1000 * 3.28084
        else:
            h = altitude_m / 1000

        if mode == DISPLAY_MODE_CENTER_SA:
            painter.drawText(int(cx - 8), int(cy + 10), f"{h:.1f}")
        elif mode == DISPLAY_MODE_NGAS:
            painter.drawText(int(cx + 10), int(cy - 10), f"{h:.1f}")
        else:
            painter.drawText(int(cx + 10), int(cy - 10), f"{h:.1f}")

    def _draw_friends(self, painter, cx, cy, plane_data, team_members,
                      scale, radius_interval, max_radius, heading_offset):
        if not team_members:
            return
        for member in team_members:
            if int(time.time()) - member.get("timestamp", 0) > config.show_friend_time:
                continue
            draw_friend_plane(painter, cx, cy, plane_data, member,
                              scale, radius_interval, max_radius, heading_offset)

    def _draw_enemies(self, painter, cx, cy, plane_data, message_dic,
                      scale, radius_interval, max_radius,
                      heading_offset, display_metric):
        for key, msg in message_dic.items():
            # OCR 路径保留旧的 times>1 降噪；钩子文本可信，第一条就要画
            if msg.get("source") != "hook" and msg.get("times", 0) <= 1:
                continue

            distance_m, bearing = calculate_bearing_and_distance(
                plane_data["x"], plane_data["z"], msg["x"], msg["z"]
            )

            if display_metric == "nm":
                distance = distance_m / 1852
            else:
                distance = distance_m / 1000

            alt_display = convert_altitude(msg["enemy_altitude"],
                                           _data_metric(msg), display_metric)

            elapsed = (int(time.time()) - msg["timeStamp"]) // TIME_ELAPSE_DIVISOR
            elapsed = min(elapsed, TIME_ELAPSE_MAX_LEVEL)

            draw_enemy_plane(painter, cx, cy, bearing, distance, msg,
                             alt_display, scale, radius_interval,
                             max_radius, elapsed, heading_offset)

    def _draw_bullseyes(self, painter, cx, cy, plane_data, bullseye_dic,
                        scale, radius_interval, max_radius,
                        heading_offset, display_metric):
        for key, msg in bullseye_dic.items():
            if msg.get("times", 0) < 1:
                continue

            distance_m, bearing = calculate_bearing_and_distance(
                plane_data["x"], plane_data["z"], msg["x"], msg["z"]
            )

            if display_metric == "nm":
                distance = distance_m / 1852
            else:
                distance = distance_m / 1000

            alt_display = convert_altitude(msg.get("bulls_enemy_altitude", 0),
                                           _data_metric(msg), display_metric)

            elapsed = (int(time.time()) - msg["timeStamp"]) // TIME_ELAPSE_DIVISOR
            elapsed = min(elapsed, TIME_ELAPSE_MAX_LEVEL)

            draw_enemy_plane(painter, cx, cy, bearing, distance, msg,
                             alt_display, scale, radius_interval,
                             max_radius, elapsed, heading_offset)
