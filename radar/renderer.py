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
)
from config import config
from radar.grid import draw_radar_grid, draw_aircraft_arrow, draw_altitude_label
from radar.aircraft import draw_enemy_plane, draw_friend_plane
from utils import calculate_bearing_and_distance
from ocr.parser import convert_altitude, convert_distance


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
            if msg.get("times", 0) <= 1:
                continue

            distance_m, bearing = calculate_bearing_and_distance(
                plane_data["x"], plane_data["z"], msg["x"], msg["z"]
            )

            if display_metric == "nm":
                distance = distance_m / 1852
            else:
                distance = distance_m / 1000

            alt_display = convert_altitude(msg["enemy_altitude"],
                                           config.awacs_metric_unit, display_metric)

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
                                           config.awacs_metric_unit, display_metric)

            elapsed = (int(time.time()) - msg["timeStamp"]) // TIME_ELAPSE_DIVISOR
            elapsed = min(elapsed, TIME_ELAPSE_MAX_LEVEL)

            draw_enemy_plane(painter, cx, cy, bearing, distance, msg,
                             alt_display, scale, radius_interval,
                             max_radius, elapsed, heading_offset)
