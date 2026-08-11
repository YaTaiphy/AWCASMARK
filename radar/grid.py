# -*- coding: utf-8 -*-
"""雷达网格绘制 — 三种显示模式共享的同心圆、径向线、方向标识绘制逻辑。"""

import math
from PySide6.QtCore import Qt, QPoint, QPointF
from PySide6.QtGui import QPainter, QPen, QColor, QPolygonF
from constants import (
    GRID_COLOR, GRID_LINE_WIDTH, TEXT_COLOR,
    CENTER_COLOR, ARROW_COLOR, ARROW_HEAD_FILL,
    ALTITUDE_LABEL_COLOR, DASH_PATTERN, ANGLE_STEP,
)


def draw_radar_grid(painter: QPainter, center_x: float, center_y: float,
                    num_circles: int, radius_interval: float, max_radius: float,
                    heading_offset: float = 0.0):
    """绘制雷达网格：同心圆 + 径向线 + 方向标识 + 角度刻度。

    Args:
        painter: QPainter 实例
        center_x, center_y: 雷达中心坐标
        num_circles: 同心圆数量
        radius_interval: 同心圆间距 (像素)
        max_radius: 最大圆半径 (像素)
        heading_offset: 航向偏移角度 (度)。0 = 北向上 (NGAS)，非0 = 机头向上 (SA)
    """
    painter.setRenderHint(QPainter.Antialiasing)

    # ---- 画笔设置 ----
    pen = QPen()
    pen.setColor(GRID_COLOR)
    pen.setWidth(GRID_LINE_WIDTH)
    pen.setStyle(Qt.DashLine)
    pen.setDashPattern(DASH_PATTERN)
    painter.setPen(pen)

    # ---- 1. 同心圆 ----
    for i in range(1, num_circles + 1):
        radius = i * radius_interval
        painter.drawEllipse(QPoint(int(center_x), int(center_y)), int(radius), int(radius))

    # ---- 2. 径向直线 ----
    for angle_deg in range(0, 360, ANGLE_STEP):
        angle_rad = math.radians(angle_deg)
        end_x = center_x + max_radius * math.cos(angle_rad)
        end_y = center_y + max_radius * math.sin(angle_rad)
        painter.drawLine(
            QPointF(center_x, center_y),
            QPointF(end_x, end_y),
        )

    # ---- 3. 方向标识和角度文字 ----
    pen.setStyle(Qt.SolidLine)
    pen.setColor(TEXT_COLOR)
    painter.setPen(pen)

    font = painter.font()
    font.setPointSize(12)
    font.setBold(True)
    painter.setFont(font)

    directions = {"N": 0, "S": 180, "E": 90, "W": 270}
    text_offset = 15

    for direction, angle_deg in directions.items():
        math_angle_deg = (90 + angle_deg - heading_offset) % 360
        angle_rad = math.radians(math_angle_deg)
        tx = center_x - (max_radius + text_offset) * math.cos(angle_rad)
        ty = center_y - (max_radius + text_offset) * math.sin(angle_rad)
        painter.drawText(int(tx - 10), int(ty + 5), direction)

    angle_text_offset = 20
    for angle_deg in range(0, 360, ANGLE_STEP):
        if angle_deg in directions.values():
            continue
        math_angle_deg = (90 + angle_deg - heading_offset) % 360
        angle_rad = math.radians(math_angle_deg)
        tx = center_x - (max_radius + angle_text_offset) * math.cos(angle_rad)
        ty = center_y - (max_radius + angle_text_offset) * math.sin(angle_rad)
        painter.drawText(int(tx - 15), int(ty + 7), f"{angle_deg}°")

    # ---- 4. 中心点 ----
    pen.setStyle(Qt.SolidLine)
    pen.setColor(CENTER_COLOR)
    painter.setPen(pen)
    painter.drawEllipse(QPoint(int(center_x), int(center_y)), 3, 3)


def draw_aircraft_arrow(painter: QPainter, center_x: float, center_y: float,
                        heading_deg: float, radius_interval: float):
    """绘制本机位置的航向箭头。

    Args:
        heading_deg: 飞机航向 (0=北, 90=东, 180=南, 270=西)
    """
    pen = QPen()
    pen.setColor(ARROW_COLOR)
    pen.setWidth(2)
    pen.setStyle(Qt.SolidLine)
    painter.setPen(pen)

    arrow_length = radius_interval / 4
    # 航向 → 数学角度 (0=右, 90=上)
    math_angle = math.radians(heading_deg + 90)

    end_x = center_x - arrow_length * math.cos(math_angle)
    end_y = center_y - arrow_length * math.sin(math_angle)

    painter.drawLine(
        QPointF(center_x, center_y),
        QPointF(end_x, end_y),
    )

    # 箭头头部三角形
    _draw_arrow_head(painter, end_x, end_y, math_angle, radius_interval / 20)


def _draw_arrow_head(painter: QPainter, tip_x: float, tip_y: float,
                     angle_rad: float, head_size: float):
    """在指定位置绘制箭头头部三角形。

    Args:
        tip_x, tip_y: 箭头尖端坐标
        angle_rad: 箭头方向 (数学角度，弧度)
        head_size: 箭头头部大小 (像素)
    """
    arrow_angle = math.radians(30)

    a1 = angle_rad + arrow_angle
    a2 = angle_rad - arrow_angle

    p1 = QPointF(tip_x + head_size * math.cos(a1),
                 tip_y - head_size * math.sin(a1))
    p2 = QPointF(tip_x + head_size * math.cos(a2),
                 tip_y - head_size * math.sin(a2))

    arrow_head = QPolygonF([QPointF(tip_x, tip_y), p1, p2])
    painter.setBrush(ARROW_HEAD_FILL)
    painter.drawPolygon(arrow_head)


def draw_altitude_label(painter: QPainter, center_x: float, center_y: float,
                        altitude_m: float, display_metric: str):
    """在中心点附近绘制本机高度标签。

    Args:
        altitude_m: 高度 (米)
        display_metric: 显示单位 "km" 或 "nm"
    """
    font = painter.font()
    font.setPointSize(6)
    font.setBold(True)
    painter.setFont(font)
    painter.setPen(ALTITUDE_LABEL_COLOR)

    if display_metric == "nm":
        h = altitude_m / 1000 * 3.28084  # 米 → 千英尺
    else:
        h = altitude_m / 1000

    painter.drawText(int(center_x + 10), int(center_y - 10), f"{h:.1f}")
