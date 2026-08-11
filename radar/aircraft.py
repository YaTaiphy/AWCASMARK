# -*- coding: utf-8 -*-
"""飞机标记绘制 — 参数化统一绘制敌机/友机 × 绝对/相对方位。

将原有的 4 个独立函数 (drawFriendPlaneByBearingAndDistance{Abs,SA}Scale
+ drawEnemyPlaneByBearingAndDistance{Abs,SA}Scale) 合并为 2 个参数化函数。
"""

import math
from PySide6.QtCore import Qt, QPoint, QPointF
from PySide6.QtGui import QPen, QColor, QPolygonF, QFont, QPainter

from constants import (
    TIME_COLOR_MAP, FRIENDS_COLOR, SERVER_MODE_SPS, SERVER_MODE_BSC,
    CONDITION_HOT, ARROW_HEAD_FILL, TEXT_COLOR, AIRCRAFT_LABEL_COLOR,
)
from config import config


def draw_enemy_plane(painter: QPainter, center_x: float, center_y: float,
                     bearing_deg: float, distance: float, message: dict,
                     height_display: float, scale: float,
                     radius_interval: float, max_radius: float,
                     time_elapse: int, heading_offset: float = 0.0):
    """绘制一个敌机标记。

    Args:
        heading_offset: 航向偏移。0 = 绝对方位 (NGAS)；非0 = 相对方位 (SA)
        height_display: 显示用高度 (千英尺或千米)
    """
    enemy_heading = message.get("enemy_heading", -1)
    condition = message.get("condition", -2)

    if distance > scale:
        return

    color = TIME_COLOR_MAP.get(time_elapse, TIME_COLOR_MAP[7])
    painter.setBrush(color)

    # 方位角 → 数学角度 → 屏幕坐标
    direction_angle = bearing_deg + 90 - heading_offset
    angle_rad = math.radians(direction_angle)
    distance_pixels = (distance / scale) * max_radius

    ex = center_x - distance_pixels * math.cos(angle_rad)
    ey = center_y - distance_pixels * math.sin(angle_rad)

    # ---- 标记点 ----
    pen = QPen()
    pen.setStyle(Qt.SolidLine)
    pen.setColor(color)
    painter.setPen(pen)
    painter.drawEllipse(QPoint(int(ex), int(ey)), 3, 3)

    # ---- 文字标签 (跟随标记点颜色随时间淡出) ----
    font = QFont()
    font.setPointSize(8 if heading_offset == 0 else 6)
    painter.setFont(font)
    painter.setPen(color)
    painter.drawText(int(ex + 6), int(ey - 3), f"{height_display:.1f}")

    # ---- SPS/BSC 模式附加信息 ----
    mode = config.server_mode
    if mode == SERVER_MODE_SPS:
        mach = message.get("speed", 0)
        painter.drawText(int(ex + 6), int(ey + 6), f"M{mach:.2f}")
        cs = message.get("callsign", "")
        painter.drawText(int(ex + 6), int(ey - 12), str(cs))
    elif mode == SERVER_MODE_BSC:
        cs = message.get("callsign", "")
        painter.drawText(int(ex + 6), int(ey - 12), str(cs))

    # ---- 航向箭头 ----
    if enemy_heading < 0:
        return

    arrow_angle_rad = math.radians((enemy_heading + 90 - heading_offset) % 360)
    arrow_length = max_radius / 20

    tip_x = ex - arrow_length * math.cos(arrow_angle_rad)
    tip_y = ey - arrow_length * math.sin(arrow_angle_rad)

    pen.setColor(color)
    pen.setWidth(2)
    painter.setPen(pen)

    # 所有 condition (HOT/COLD/FLANK) 统一从敌机圆点画线
    # heading 已在 _heading_from_condition 中根据接敌状态计算好：
    #   HOT:  (bearing + 180) → 箭头指向本机
    #   COLD: bearing        → 箭头背离本机
    #   FLANK: (bearing + 90) → 箭头垂直方位线
    painter.drawLine(QPointF(ex, ey), QPointF(tip_x, tip_y))

    # 箭头头部
    head_size = radius_interval / 20
    arrow_spread = math.radians(30)
    a1 = arrow_angle_rad + arrow_spread
    a2 = arrow_angle_rad - arrow_spread
    p1 = QPointF(tip_x + head_size * math.cos(a1), tip_y - head_size * math.sin(a1))
    p2 = QPointF(tip_x + head_size * math.cos(a2), tip_y - head_size * math.sin(a2))
    painter.drawPolygon(QPolygonF([QPointF(tip_x, tip_y), p1, p2]))
    painter.setBrush(ARROW_HEAD_FILL)


def draw_friend_plane(painter: QPainter, center_x: float, center_y: float,
                      plane_data: dict, member: dict,
                      scale: float, radius_interval: float, max_radius: float,
                      heading_offset: float = 0.0):
    """绘制一个友机标记。

    Args:
        plane_data: 本机数据 {x, z, heading}
        member: 友机数据 {x, y, z, heading, callSign, timestamp}
        heading_offset: 0=绝对方位, 非0=相对方位
    """
    from utils import calculate_bearing_and_distance

    painter.setBrush(FRIENDS_COLOR)

    distance_m, bearing = calculate_bearing_and_distance(
        plane_data["x"], plane_data["z"], member["x"], member["z"]
    )

    if config.show_metrics == "nm":
        distance = distance_m / 1852
        height_display = member["y"] / 1000 * 3.28084
    else:
        distance = distance_m / 1000
        height_display = member["y"] / 1000

    if distance > scale:
        return

    direction_angle = bearing + 90 - heading_offset
    angle_rad = math.radians(direction_angle)
    distance_pixels = (distance / scale) * max_radius

    ex = center_x - distance_pixels * math.cos(angle_rad)
    ey = center_y - distance_pixels * math.sin(angle_rad)

    # ---- 标记点 ----
    pen = QPen()
    pen.setStyle(Qt.SolidLine)
    pen.setColor(FRIENDS_COLOR)
    painter.setPen(pen)
    painter.drawEllipse(QPoint(int(ex), int(ey)), 3, 3)

    # ---- 高度 + 呼号 (浅色文字, 始终可读) ----
    font = QFont()
    font.setPointSize(8)
    painter.setFont(font)
    painter.setPen(AIRCRAFT_LABEL_COLOR)
    painter.drawText(int(ex + 6), int(ey - 3), f"{height_display:.1f}")
    painter.drawText(int(ex + 6), int(ey + 6), member.get("callSign", ""))

    # ---- 航向箭头 ----
    arrow_angle_rad = math.radians((member["heading"] + 90 - heading_offset) % 360)
    arrow_length = max_radius / 20

    tip_x = ex - arrow_length * math.cos(arrow_angle_rad)
    tip_y = ey - arrow_length * math.sin(arrow_angle_rad)

    pen.setColor(FRIENDS_COLOR)
    pen.setWidth(2)
    painter.setPen(pen)
    painter.drawLine(QPointF(ex, ey), QPointF(tip_x, tip_y))

    # 箭头头部
    head_size = radius_interval / 20
    arrow_spread = math.radians(30)
    a1 = arrow_angle_rad + arrow_spread
    a2 = arrow_angle_rad - arrow_spread
    p1 = QPointF(tip_x + head_size * math.cos(a1), tip_y - head_size * math.sin(a1))
    p2 = QPointF(tip_x + head_size * math.cos(a2), tip_y - head_size * math.sin(a2))
    painter.drawPolygon(QPolygonF([QPointF(tip_x, tip_y), p1, p2]))
    painter.setBrush(ARROW_HEAD_FILL)
