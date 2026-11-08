# -*- coding: utf-8 -*-
"""通报文本解析 — 支持传统预警机 (AWACS BRA)、SPS 面板、BSC 面板、牛眼通报四种格式。

预警机通报文本解析：SPS / BSC 面板、传统 BRA、牛眼，以及中英文两种风格。
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
# 数值提取
# =============================================================================

def _first_number(text: str) -> str:
    """提取字符串中第一段连续数字（没有则返回空串）。"""
    match = re.search(r"\d+", text)
    return match.group() if match else ""


def _first_int(text: str, default: int = 0) -> int:
    """提取第一个整数；取不到时返回 default。"""
    value = _first_number(text)
    return int(value) if value else default


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
    """解析英文接敌状态: hot→1, flanking/flank→0, cold→-1, 未知→-2。"""
    lower = text.lower()
    if re.search(r"\bhot\b", lower):
        return CONDITION_HOT
    if re.search(r"\bcold\b", lower):
        return CONDITION_COLD
    if re.search(r"\b(flanking|flank|beam)\b", lower):
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

_CALLSIGN_STRIP = re.compile(r"[^0-9a-z]")
_RE_BRG_FOR = re.compile(r"(\d{1,3})\s*for\s*(\d{1,3}(?:\.\d+)?)", re.IGNORECASE)
_RE_ALTITUDE = re.compile(r"altitude\s+([\d,]+)", re.IGNORECASE)


def _norm_callsign(text: str) -> str:
    """归一化呼号：小写并去掉空格、连字符等分隔符。

    "Uzi 1-1" / "UZI-11" / "uzi11" 归一化后都是 "uzi11"，
    与配置里的 text（字母）+ num（数字）拼接结果一致。
    """
    return _CALLSIGN_STRIP.sub("", (text or "").lower())


def _match_callsign(receiver_field: str, call_sign: dict) -> bool:
    """判断通报的接收方是不是自己。

    报文格式（实机）：
        预警机 (Overlord1-1): 128, Overlord1-1, 敌情 (BRA), 351 方位, ...
        └─ 类别 ─┘ └ AWACS 自称 ┘ └接收方┘ └ 发送方 ┘

    接收方（第 0 段的冒号之后）才是自己的呼号，可能是纯数字 "128"，
    也可能是字母+数字 "Uzi 1-1"。配置拆成 text + num，这里归一化后整体比较。
    """
    receiver = receiver_field.split(":")[-1]
    got = _norm_callsign(receiver)
    if not got:
        return False

    text = str(call_sign.get("text", "") or "")
    num = str(call_sign.get("num", "") or "")
    want = _norm_callsign(text + num)
    if not want:
        return False

    if got == want:
        return True
    # 英文呼号前面可能还带着别的词（如 "108th Uzi 1-1"），允许后缀匹配；
    # 纯数字呼号则必须完全相等，避免 "128" 命中 "5128"。
    return bool(text) and got.endswith(want)


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
        enemy_altitude = _first_int(parts[-2])
        enemy_distance_raw = _first_int(parts[-3])
        enemy_bearing = _first_int(parts[-4])

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

        altitude = _first_int(parts[-1])
        distance_raw = _first_int(parts[-2])
        bearing = _first_int(parts[-3])

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


def parse_sps_panel(ocr_lines: list[str], metric_unit: str = "auto") -> list[dict]:
    """解析 SPS 服务器面板格式。

    格式: "机型 编号 方位 距离NM 高度ft 速度Knts 航向 Hot/Cold/Flank"

    metric_unit:
        "auto"    — 从每行自带的单位词判定（面板一定带 NM/ft 或 KM/m）
        "nm"/"km" — 强制按该单位校验（旧行为，用于文本单位缺失的兜底）

    Returns:
        敌机数据字典列表，额外带 "distance_unit" / "height_unit" 供上层换算
    """
    condition_feature = ["hot", "cold", "flank", "beam"]
    nm_feature = ["nm", "feet", "ft", "knts"]
    km_feature = ["km", "m"]

    # auto: 不做全行单位过滤，交给每行的单位词判定
    if metric_unit == "auto":
        unit_features = None
    elif metric_unit == "km":
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

        if unit_features is not None and not any(feat in lower for feat in unit_features):
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
                # 每行自带单位：上层据此换算，不再依赖全局配置
                "distance_unit": "nm" if "nm" in dist_unit else "km",
                "height_unit": "ft" if "ft" in height_unit else "m",
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

    Returns:
        新识别的敌机消息列表
    """
    from utils import offset_coordinate

    results = []
    for line in ocr_lines:
        if not line or not line.strip():
            continue

        lower = line.lower().strip()
        if " for " not in lower or "altitude" not in lower:
            continue

        bd = _RE_BRG_FOR.search(lower)
        alt = _RE_ALTITUDE.search(lower)
        if not bd or not alt:
            continue

        enemy_bearing = int(bd.group(1))
        enemy_distance_raw = float(bd.group(2))
        if not 0 <= enemy_bearing < 360:
            continue

        enemy_altitude = _first_int(alt.group(1))

        if not _match_callsign_en(line, call_sign):
            continue

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

    Returns:
        新识别的牛眼敌机消息列表
    """
    from utils import offset_coordinate

    results = []
    for line in ocr_lines:
        if not line or not line.strip():
            continue

        lower = line.lower().strip()
        if "bull" not in lower:
            continue

        bd = _RE_BRG_FOR.search(lower)
        if not bd:
            continue

        bearing = int(bd.group(1))
        distance_raw = float(bd.group(2))
        if not 0 <= bearing < 360:
            continue

        alt = _RE_ALTITUDE.search(lower)
        altitude = _first_int(alt.group(1)) if alt else 0

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

def _match_callsign_en(line: str, call_sign: dict) -> bool:
    """英文通报的接收方在第 0 段（第一个逗号之前），复用统一的归一化比较。

    例："Dodge 4, Overlord1-1, pop-up group, ..." → 接收方 "Dodge 4"。
    """
    receiver = line.split(",")[0]
    return _match_callsign(receiver, call_sign)
