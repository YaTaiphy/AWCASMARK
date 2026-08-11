# -*- coding: utf-8 -*-
"""纯数学工具函数 — 坐标计算、方位/距离、坐标格式转换。

本模块不依赖 Qt 或项目配置，仅使用 Python 标准库 math。
原 drawing/network/OCR 函数已迁移至 radar/、network/、ocr/ 包。
"""

import math
import re


# =============================================================================
# DCS 平面坐标计算
# =============================================================================

def offset_coordinate(x, z, distance_m, bearing_deg):
    """在DCS平面坐标系中，根据起始点、距离和方位角计算偏移后的坐标。

    Args:
        x: 起始X坐标（北向，米）
        z: 起始Z坐标（东向，米）
        distance_m: 偏移距离（米）
        bearing_deg: 方位角（度，0°=北，90°=东，180°=南，270°=西）

    Returns:
        (new_x, new_z): 偏移后的坐标（米）
    """
    bearing_rad = math.radians(bearing_deg)
    dx = distance_m * math.cos(bearing_rad)
    dz = distance_m * math.sin(bearing_rad)
    return x + dx, z + dz


def calculate_bearing_and_distance(x1, z1, x2, z2):
    """在DCS平面坐标系中，计算B点相对于A点的距离和方位角。

    Args:
        x1, z1: A点坐标（北向，东向，米）
        x2, z2: B点坐标（北向，东向，米）

    Returns:
        (distance_m, bearing_deg): 距离（米），方位角（度，0°=北，90°=东）
    """
    dx = x2 - x1
    dz = z2 - z1
    distance_m = math.sqrt(dx * dx + dz * dz)
    bearing_rad = math.atan2(dz, dx)
    bearing_deg = math.degrees(bearing_rad)
    bearing_deg = (bearing_deg + 360) % 360
    return distance_m, bearing_deg


def bullsEyeCaculation(bullseye_x, bullseye_z, enemy_bearing, enemy_distance,
                       plane_x, plane_z, metric_unit):
    """计算敌机相对于本机的方位和距离（基于牛眼坐标）。

    Args:
        bullseye_x, bullseye_z: 牛眼坐标（米）
        enemy_bearing: 敌机相对于牛眼的方位角（度）
        enemy_distance: 敌机相对于牛眼的距离（km 或 nm）
        plane_x, plane_z: 本机坐标（米）
        metric_unit: 单位 "km" 或 "nm"

    Returns:
        (distance_to_enemy, bearing_to_enemy): 距离和方位角
    """
    if metric_unit == "nm":
        enemy_distance_m = enemy_distance * 1852
    else:
        enemy_distance_m = enemy_distance * 1000

    enemy_x, enemy_z = offset_coordinate(bullseye_x, bullseye_z,
                                         enemy_distance_m, enemy_bearing)
    distance_m, bearing = calculate_bearing_and_distance(plane_x, plane_z,
                                                         enemy_x, enemy_z)
    if metric_unit == "nm":
        distance_m /= 1852
    else:
        distance_m /= 1000
    return distance_m, bearing


# =============================================================================
# 坐标格式转换 (度分 → 十进制度)
# =============================================================================

def dm_to_dd(degrees, minutes):
    """将度分格式转换为十进制度。"""
    return degrees + minutes / 60


def parse_dm_coordinate(coord_str):
    """解析度分格式坐标字符串，如 "N 42°10.659'"。

    Returns:
        (direction, degrees, minutes)
    """
    coord_str = coord_str.strip()
    direction = coord_str[0]
    match = re.search(r"(\d+)°(\d+\.\d+)\'", coord_str)
    if match:
        degrees = float(match.group(1))
        minutes = float(match.group(2))
        return direction, degrees, minutes
    raise ValueError(f"无法解析坐标格式: {coord_str}")


def convert_to_decimal(coord_str):
    """将度分格式坐标字符串转换为十进制度数值。"""
    direction, degrees, minutes = parse_dm_coordinate(coord_str)
    decimal_value = dm_to_dd(degrees, minutes)
    if direction in ("S", "W"):
        decimal_value = -decimal_value
    return decimal_value


def format_as_numeric(decimal_value, decimals=4):
    """格式化为指定位小数的数字字符串，如 44.9666。"""
    return f"{decimal_value:.{decimals}f}"
