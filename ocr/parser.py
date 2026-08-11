# -*- coding: utf-8 -*-
"""通报文本解析 — 支持传统预警机 (AWACS BRA)、SPS 面板、BSC 面板、牛眼通报四种格式。

消除 wordsOCRFlask.py 和 wordsOCR.py 中的重复解析逻辑，
统一为四个独立、可测试的解析函数。
"""

import re
from typing import Optional

from constants import (
    NM_TO_M, KM_TO_M, M_TO_FT,
    CONDITION_HOT, CONDITION_COLD, CONDITION_FLANK, CONDITION_UNKNOWN,
)
from log import get_logger

logger = get_logger(__name__)


# =============================================================================
# OCR 纠错
# =============================================================================

def _correct_numbers(text: str) -> str:
    """对常见数字 OCR 识别错误进行纠正。"""
    mapping = str.maketrans({
        "o": "0", "O": "0", "c": "0",
        "l": "1", "I": "1", "i": "1", "L": "1", "/": "1", "\\": "1",
        "b": "6", "B": "8", "G": "6",
        "g": "9", "q": "9", "Q": "9",
        "s": "5", "S": "5",
        "z": "2", "Z": "2",
        "T": "7", "t": "7",
    })
    return text.translate(mapping)


def _correct_letters(text: str) -> str:
    """对常见字母 OCR 识别错误进行纠正。"""
    mapping = str.maketrans({
        "0": "O", "8": "B", "6": "G", "9": "Q", "5": "S",
        "1": "I", "2": "Z", "4": "A", "7": "T", "3": "E",
    })
    return text.translate(mapping)


def _first_number(text: str) -> str:
    """提取字符串中第一段连续数字。"""
    match = re.search(r"\d+", text)
    return match.group() if match else ""


# =============================================================================
# 单位转换
# =============================================================================

def convert_distance(value: float, metric_unit: str) -> float:
    """将 OCR 读出的距离转换为米。"""
    if metric_unit == "nm":
        return value * NM_TO_M
    else:
        return value * KM_TO_M


def convert_altitude(value: float, data_metric: str, display_metric: str) -> float:
    """将高度值转换为显示用的千单位 (千英尺或千米)。

    data_metric: 原始数据单位 ("nm" = 英尺, "km" = 米)
    display_metric: 显示单位 ("nm" = 千英尺, "km" = 千米)
    """
    value_km = value / 1000  # 原始值 → 千米
    if display_metric == "nm":
        # 要求显示为千英尺
        if data_metric == "nm":
            return value_km  # 已是千英尺 (原始值英尺/1000)
        else:
            return value_km * M_TO_FT  # 米 → 千英尺
    else:
        # 要求显示为千米
        if data_metric == "nm":
            return value_km / M_TO_FT  # 千英尺 → 千米
        else:
            return value_km  # 米 → 千米


# =============================================================================
# 对接状态判定
# =============================================================================

def _parse_condition(text: str) -> int:
    """从文本片段解析对接状态: 迎头→1, 追击→-1, 侧对→0, 未知→-2。"""
    if "头" in text or "迎" in text:
        return CONDITION_HOT
    elif "追" in text or "尾" in text:
        return CONDITION_COLD
    elif "侧" in text or "对" in text:
        return CONDITION_FLANK
    return CONDITION_UNKNOWN


def _parse_condition_en(text: str) -> int:
    """Parse English aspect: hot→1, flanking/flank→0, cold→-1, unknown→-2。

    OCR 容错: hot 可能识别为 jot/h0t/j0t 等 (h↔j, o↔0, t↔7)。
    """
    lower = text.lower()
    # "hot" 模糊匹配 — 常见 OCR 错误: jot, h0t, j0t, ho7
    if re.search(r'\b[hj][o0][t7]\b', lower):
        return CONDITION_HOT
    # "cold" 模糊匹配 — OCR 错误: c0ld, co1d, cold
    if re.search(r'\b[c][o0][l1][d]\b', lower):
        return CONDITION_COLD
    if "flanking" in lower or "flank" in lower or "beam" in lower:
        return CONDITION_FLANK
    return CONDITION_UNKNOWN


def _heading_from_condition(bearing: int, condition: int) -> int:
    """根据方位角和对接状态推算敌机航向。"""
    if condition == CONDITION_HOT:
        return (bearing + 180) % 360
    elif condition == CONDITION_COLD:
        return bearing
    elif condition == CONDITION_FLANK:
        return (bearing + 90) % 360
    return -1


# =============================================================================
# 呼号匹配
# =============================================================================

def _match_callsign(ocr_text: str, call_sign: dict) -> bool:
    """检查 OCR 识别的呼号是否匹配配置的呼号。"""
    if call_sign["text"] == "":
        # 仅数字呼号
        ocr_num = _correct_numbers(ocr_text.split(":")[-1].strip())
        return call_sign["num"] == ocr_num
    else:
        ocr_parts = ocr_text.split(":")[-1].strip()
        ocr_num = _correct_numbers(ocr_parts[-len(call_sign["num"]):])
        if call_sign["num"] != ocr_num:
            return False
        if ocr_parts:
            ocr_first = _correct_letters(ocr_parts[0]).lower()
            expected_first = call_sign["text"][0].lower()
            return ocr_first == expected_first
        return False


# =============================================================================
# 主解析函数
# =============================================================================

def parse_awacs_bra(ocr_lines: list[str], call_sign: dict, metric_unit: str,
                    plane_x: float, plane_z: float) -> list[dict]:
    """解析传统预警机 BRA 通报 (7 段格式)。

    格式: "预警机(Callsign): 呼号, 接收方, 敌情(BRA), 方位, 距离, 高度, 接敌状态"

    Returns:
        新识别的敌机消息列表，每条为包含 x/z/enemy_altitude/enemy_heading/condition 的字典
    """
    from utils import offset_coordinate

    results = []
    for line in ocr_lines:
        # 标准化标点
        normalized = (line.replace("，", ",").replace("：", ":")
                      .replace(".", ",").replace("。", ",")
                      .replace("、", ",").replace(";", ","))
        parts = [p.strip() for p in normalized.split(",") if p.strip()]

        need_words = ["方", "位置", "距", "离", "高", "度"]
        if len(parts) != 7 or not ("方" in line or "位" in line):
            continue

        # 呼号匹配
        if not _match_callsign(parts[0], call_sign):
            continue

        # 接敌状态
        condition = _parse_condition(parts[-1])

        # 提取数值 (bearing, distance, altitude)
        enemy_altitude = int("".join(re.findall(r"\d+", "0" + _correct_numbers(parts[-2]))))
        enemy_distance_raw = int("".join(re.findall(r"\d+", "0" + _correct_numbers(parts[-3]))))
        enemy_bearing = int("".join(re.findall(r"\d+", "0" + _correct_numbers(parts[-4]))))

        if enemy_bearing < 0 or enemy_bearing >= 360:
            continue

        enemy_distance = convert_distance(enemy_distance_raw, metric_unit)
        enemy_heading = _heading_from_condition(enemy_bearing, condition)

        new_x, new_z = offset_coordinate(plane_x, plane_z, enemy_distance, enemy_bearing)

        results.append({
            "enemy_altitude": enemy_altitude,
            "enemy_heading": enemy_heading,
            "x": new_x,
            "z": new_z,
            "condition": condition,
            "bearing": enemy_bearing,
            "distance": enemy_distance,
        })
    return results


def parse_bullseye(ocr_lines: list[str], metric_unit: str,
                   bullseye_x: float, bullseye_z: float) -> list[dict]:
    """解析牛眼通报 (3 段格式)。

    格式: "机型, 方位距离, 高度"

    Returns:
        新识别的牛眼敌机消息列表
    """
    from utils import offset_coordinate

    results = []
    need_words = ["方", "位置", "距", "离", "高", "度"]

    for line in ocr_lines:
        normalized = (line.replace("，", ",").replace("：", ":")
                      .replace(".", ",").replace("。", ",")
                      .replace("、", ",").replace(";", ","))
        parts = [p.strip() for p in normalized.split(",") if p.strip()]

        # 牛眼: 3 段，第一段含 "机" 或 "队"，且有方位/距离/高度关键词
        if len(parts) != 3:
            continue
        if not ("机" in parts[0] or "队" in parts[0]):
            continue
        if not any(word in line for word in need_words):
            continue

        altitude = int("".join(re.findall(r"\d+", "0" + _correct_numbers(parts[-1]))))
        distance_raw = int("".join(re.findall(r"\d+", "0" + _correct_numbers(parts[-2]))))
        bearing = int("".join(re.findall(r"\d+", "0" + _correct_numbers(parts[-3]))))

        if bearing < 0 or bearing >= 360:
            continue

        distance = convert_distance(distance_raw, metric_unit)
        new_x, new_z = offset_coordinate(bullseye_x, bullseye_z, distance, bearing)

        results.append({
            "bulls_enemy_altitude": altitude,
            "x": new_x,
            "z": new_z,
            "enemy_heading": -1,
            "condition": 0,
        })
    return results


def parse_sps_panel(ocr_lines: list[str], metric_unit: str) -> list[dict]:
    """解析 SPS 服务器面板格式。

    格式: "机型 编号 方位 距离NM 高度ft 速度Knts 航向 Hot/Cold/Flank"

    Returns:
        敌机数据字典列表
    """
    condition_feature = ["hot", "cold", "flank", "beam"]
    nm_feature = ["nm", "feet", "ft", "knts"]
    km_feature = ["km", "m"]

    # 根据配置选择特征词
    if metric_unit == "km":
        unit_features = km_feature
    else:
        unit_features = nm_feature

    results = []
    for line in ocr_lines:
        if not line or not line.strip():
            continue

        lower = line.lower()

        # 检查是否含有关键词
        mark = ""
        for cond in condition_feature:
            if cond in lower:
                mark = cond
                break
        if not mark:
            continue

        if not any(feat in lower for feat in unit_features):
            continue

        parts = lower.split()
        if len(parts) < 10:
            continue

        # 确定关键词位置
        condition_index = -1
        for i, part in enumerate(parts):
            if mark in part:
                condition_index = i
                break
        if condition_index < 8:
            continue

        try:
            heading = int(parts[condition_index - 1])

            # 速度单位检查
            speed_unit = parts[condition_index - 2].lower()
            if not ("knts" in speed_unit or "km" in speed_unit):
                continue

            speed = float(parts[condition_index - 3])
            if "knts" in speed_unit:
                from constants import KTS_TO_MACH
                speed = speed * KTS_TO_MACH
            else:
                from constants import KMH_TO_MACH
                speed = speed * KMH_TO_MACH

            # 高度单位检查
            height_unit = parts[condition_index - 4].lower()
            if not ("ft" in height_unit or "m" in height_unit):
                continue

            height_str = parts[condition_index - 5].replace(",", "")
            height = float(height_str)

            # 距离单位检查
            dist_unit = parts[condition_index - 6].lower()
            if not ("nm" in dist_unit or "km" in dist_unit):
                continue

            distance_str = parts[condition_index - 7].replace(",", ".")
            distance = float(distance_str)

            bearing = int(parts[condition_index - 8])
            callsign = _first_number(parts[0])
            if not callsign:
                continue

            results.append({
                "callsign": callsign,
                "bearing": bearing,
                "distance": distance,
                "height": height,
                "speed": speed,
                "heading": heading,
            })
        except (ValueError, IndexError) as exc:
            logger.warning("解析 SPS 消息时发生错误: %s", exc)
            continue

    return results


def parse_bsc_panel(ocr_lines: list[str], metric_unit: str) -> list[dict]:
    """解析 BSC 服务器面板格式。

    格式: "机型 方位° 距离NM 高度ft 航向 Hot/Cold/Flank"

    Returns:
        敌机数据字典列表
    """
    condition_feature = ["hot", "cold", "flank", "beam"]
    if metric_unit == "km":
        dist_unit_word = "km"
        height_unit_word = "m"
    else:
        dist_unit_word = "nm"
        height_unit_word = "ft"

    results = []
    for line in ocr_lines:
        if not line or not line.strip():
            continue

        lower = line.lower()

        mark = ""
        for cond in condition_feature:
            if cond in lower:
                mark = cond
                break
        if not mark:
            continue

        if dist_unit_word not in lower and height_unit_word not in lower:
            continue

        parts = lower.split()

        # 查找方位角 (含 ° 或 * 的部分)
        bearing_part = next((p for p in parts if "°" in p or "*" in p), None)
        if bearing_part is None:
            continue
        bearing = int(re.search(r"\d+", bearing_part).group())

        callsign = parts[0][0] if parts[0] else ""

        # 查找条件关键词位置
        condition_index = -1
        for i, part in enumerate(parts):
            if mark in part:
                condition_index = i
                break
        if condition_index == -1:
            continue

        try:
            if "hot" in parts[condition_index]:
                heading = (bearing + 180) % 360
                condition = CONDITION_HOT
            elif "cold" in parts[condition_index]:
                heading = bearing
                condition = CONDITION_COLD
            elif "flank" in parts[condition_index]:
                heading = (bearing + 90) % 360
                condition = CONDITION_FLANK
            elif "beam" in parts[condition_index]:
                heading = (bearing + 270) % 360
                condition = CONDITION_FLANK

            if metric_unit == "km":
                dist_part = next((p for p in parts if "km" in p), None)
                height_part = next((p for p in parts if "m" in p), None)
                if dist_part is None or height_part is None:
                    continue
            else:
                dist_part = next((p for p in parts if "nm" in p), None)
                height_part = next((p for p in parts if "ft" in p), None)
                if dist_part is None or height_part is None:
                    continue

            distance = float(re.search(r"[\d.]+", dist_part).group())
            height = float(re.search(r"[\d.]+", height_part).group())

            results.append({
                "callsign": callsign,
                "bearing": bearing,
                "distance": distance,
                "height": height,
                "heading": heading,
                "condition": condition,
            })
        except (ValueError, IndexError, AttributeError) as exc:
            logger.warning("解析 BSC 消息时发生错误: %s", exc)
            continue

    return results


# =============================================================================
# 传统预警机 (英文) 解析 — BRA + 牛眼
# =============================================================================

def parse_awacs_bra_en(ocr_lines: list[str], call_sign: dict, metric_unit: str,
                        plane_x: float, plane_z: float) -> list[dict]:
    """解析英文 AWACS BRA 通报。

    格式: "Callsign, AWACS, threat_type, 方位 for 距离, at altitude 高度, aspect"
    示例: "Dodge 4, Overlord1-1, pop-up group, 060 for 130, at altitude 500, hot"

    容错 OCR 错误:
        - 关键词 "for":  可能识别为 f0r, tor, fo7 等
        - 关键词 "altitude": 可能识别为 albitude, a1titude 等
        - 数字: 应用 _correct_numbers 纠正 (l→1, O→0, B→8 等)

    Returns:
        新识别的敌机消息列表
    """
    from utils import offset_coordinate

    # 预编译正则
    _RE_FOR = re.compile(r'\b[f7][o0][r12]\b', re.IGNORECASE)    # "for" 容错
    _RE_ALTITUDE = re.compile(r'a[a-z0-9]*tude\s+(\d+)', re.IGNORECASE)  # altitude 容错

    results = []
    for line in ocr_lines:
        if not line or not line.strip():
            continue

        lower = line.lower().strip()

        # ---- 特征词检查（原始文本 + 模糊正则） ----
        if not _RE_FOR.search(lower):
            continue
        if not _RE_ALTITUDE.search(lower):
            continue

        # ---- 提取方位和距离: "NNN for NNN" ----
        # 先匹配结构，再对数字部分做 OCR 纠错
        bd_raw = re.search(r'(\S+)\s+for\s+(\S+)', lower)
        if not bd_raw:
            continue
        bearing_str = _correct_numbers(bd_raw.group(1))
        dist_str = _correct_numbers(bd_raw.group(2))
        # 提取纯数字
        bearing_match = re.search(r'\d+', bearing_str)
        dist_match = re.search(r'\d+', dist_str)
        if not bearing_match or not dist_match:
            continue
        enemy_bearing = int(bearing_match.group())
        enemy_distance_raw = int(dist_match.group())
        if enemy_bearing < 0 or enemy_bearing >= 360:
            continue

        # ---- 提取高度 ----
        alt_match = _RE_ALTITUDE.search(lower)
        if not alt_match:
            continue
        alt_str = _correct_numbers(alt_match.group(1))
        alt_digits = re.search(r'\d+', alt_str)
        if not alt_digits:
            continue
        enemy_altitude = int(alt_digits.group())

        # ---- 呼号匹配 (原始文本) ----
        if not _match_callsign_en(lower, call_sign):
            continue

        # ---- 接敌状态 (原始文本) ----
        condition = _parse_condition_en(lower)
        enemy_distance = convert_distance(enemy_distance_raw, metric_unit)
        enemy_heading = _heading_from_condition(enemy_bearing, condition)

        new_x, new_z = offset_coordinate(plane_x, plane_z, enemy_distance, enemy_bearing)

        results.append({
            "enemy_altitude": enemy_altitude,
            "enemy_heading": enemy_heading,
            "x": new_x,
            "z": new_z,
            "condition": condition,
            "bearing": enemy_bearing,
            "distance": enemy_distance,
        })

    return results


def parse_bullseye_en(ocr_lines: list[str], metric_unit: str,
                      bullseye_x: float, bullseye_z: float) -> list[dict]:
    """解析英文牛眼通报。

    格式: "... bullseye 方位 for 距离, at altitude 高度"
    示例:
        "First group at bullseye 060 for 40, at altitude 4500"
        "Additional group at bulls 104 for 16, at altitude 5000"

    关键点：
        - 关键词: "bull" (bulls/bullseye / OCR: bu11s, bu11seye)
        - 方位/距离: "060 for 40" → bearing=060, distance=40
        - 高度:    "at altitude 4500" → 4500（容错: albitude 等）

    Returns:
        新识别的牛眼敌机消息列表
    """
    from utils import offset_coordinate

    _RE_ALTITUDE = re.compile(r'a[a-z0-9]*tude\s+(\d+)', re.IGNORECASE)  # altitude 容错

    results = []
    for line in ocr_lines:
        if not line or not line.strip():
            continue

        lower = line.lower().strip()
        corrected = _correct_numbers(lower)

        # 关键特征词: "bull" (纠错后容忍 bu11)
        if "bull" not in corrected and "bull" not in lower:
            continue
        if "for" not in corrected:
            continue

        # ---- 提取方位和距离 ----
        bd_match = re.search(r'(\d+)\s*for\s*(\d+)', corrected)
        if not bd_match:
            continue
        bearing = int(bd_match.group(1))
        distance_raw = int(bd_match.group(2))
        if bearing < 0 or bearing >= 360:
            continue

        # ---- 提取高度 (可能没有) ----
        alt_match = _RE_ALTITUDE.search(corrected)
        altitude = int(alt_match.group(1)) if alt_match else 0

        distance = convert_distance(distance_raw, metric_unit)
        new_x, new_z = offset_coordinate(bullseye_x, bullseye_z, distance, bearing)

        results.append({
            "bulls_enemy_altitude": altitude,
            "x": new_x,
            "z": new_z,
            "enemy_heading": -1,
            "condition": 0,
        })

    return results


# =============================================================================
# 英文呼号匹配
# =============================================================================

def _match_callsign_en(ocr_text: str, call_sign: dict) -> bool:
    """检查 OCR 文本是否包含配置的英文呼号。

    英文格式: "Dodge 4" 或纯数字 "9214"
    匹配策略:
        - 如果 call_sign["text"] 为空 → 仅匹配数字
        - 否则匹配首字母 + 数字
    """
    lower = ocr_text.lower()
    num = call_sign["num"]

    # 数字必须出现
    if num not in lower:
        return False

    if call_sign["text"] == "":
        # 纯数字呼号
        return True

    # 字母呼号：首字母必须匹配（OCR 可能将整词拆开）
    first_letter = call_sign["text"][0].lower()
    # 在数字前找首字母
    num_pos = lower.find(num)
    if num_pos > 0:
        prefix = lower[:num_pos]
        if first_letter in prefix:
            return True
    return False
