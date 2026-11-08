# -*- coding: utf-8 -*-
"""把解析结果写入 message_dic / bullseye_dic —— OCR 与钩子两条路径共用。

相比旧实现（ocr/client.py 里的 _process_*）有三处行为修正：

1. **重复通报续命**：同一目标再次被播报时刷新 timeStamp 并重算坐标，
   而不是只 `times += 1`（否则持续被报的目标也会按 remaining_time 过期）。
2. **单位随消息走**：每条记录带 `data_metric`（"nm"/"km"），
   渲染时按条取，不再依赖全局 config.awacs_metric_unit。
3. **来源随消息走**：带 `source`（"ocr"/"hook"）与 `source_mode`，
   渲染层据此决定画不画马赫/机型，以及是否跳过 `times > 1` 的旧降噪门槛。
"""

import time as _time

from log import get_logger
from ocr.parser import (
    convert_distance,
    parse_awacs_bra,
    parse_awacs_bra_en,
    parse_bsc_panel,
    parse_bullseye,
    parse_bullseye_en,
    parse_sps_panel,
)
from utils import offset_coordinate

logger = get_logger(__name__)


# =============================================================================
# 通用工具
# =============================================================================

def purge_expired(dic: dict, max_age_seconds: int, now: int = None):
    """移除超过 max_age_seconds 秒的旧条目。"""
    now = int(now if now is not None else _time.time())
    for key in [k for k, v in dic.items()
                if now - v.get("timeStamp", 0) > max_age_seconds]:
        del dic[key]


def _upsert(dic: dict, key: int, payload: dict, now: int):
    """插入或刷新一条记录；刷新时更新时间戳并重算坐标。"""
    entry = dic.get(key)
    if entry is None:
        payload.setdefault("times", 1)
        payload["timeStamp"] = now
        dic[key] = payload
        return

    entry.update(payload)
    entry["timeStamp"] = now          # ← 第二次播报重置衰减
    entry["times"] = entry.get("times", 1) + 1


def _panel_unit(text_lines: list, metric_unit: str) -> str:
    """面板类的单位：文本里写明的优先，文本没有单位时才用配置兜底。"""
    text = "\n".join(text_lines).lower()
    if "nm" in text or "ft" in text or "knts" in text:
        return "nm"
    if "km" in text or " km/h" in text:
        return "km"
    return metric_unit if metric_unit in ("km", "nm") else "nm"


# =============================================================================
# 传统预警机（中文 BRA + 牛眼）
# =============================================================================

def apply_awacs(text_lines, call_sign, metric_unit, plane_x, plane_z,
                bullseye_x, bullseye_z, message_dic, bullseye_dic,
                source="ocr", now=None):
    now = int(now if now is not None else _time.time())
    unit = metric_unit if metric_unit in ("km", "nm") else "km"   # 传统通报无单位

    parsed = parse_awacs_bra(text_lines, call_sign, unit, plane_x, plane_z)
    for item in parsed:
        key = int(item["enemy_altitude"] + item["distance"] + item["bearing"]
                  + item["enemy_heading"] + item["condition"])
        _upsert(message_dic, key, {
            "enemy_altitude": item["enemy_altitude"],
            "enemy_heading": item["enemy_heading"],
            "x": item["x"],
            "z": item["z"],
            "condition": item["condition"],
            "data_metric": unit,
            "source": source,
            "source_mode": 0,
        }, now)

    bullseye_parsed = parse_bullseye(text_lines, unit, bullseye_x, bullseye_z)
    for item in bullseye_parsed:
        key = int(item["bulls_enemy_altitude"] + item["x"] + item["z"])
        _upsert(bullseye_dic, key, {
            "bulls_enemy_altitude": item["bulls_enemy_altitude"],
            "x": item["x"],
            "z": item["z"],
            "enemy_heading": -1,
            "condition": 0,
            "data_metric": unit,
            "source": source,
            "source_mode": 0,
        }, now)

    return len(parsed) + len(bullseye_parsed)


def apply_awacs_en(text_lines, call_sign, metric_unit, plane_x, plane_z,
                   bullseye_x, bullseye_z, message_dic, bullseye_dic,
                   source="ocr", now=None):
    now = int(now if now is not None else _time.time())
    unit = metric_unit if metric_unit in ("km", "nm") else "nm"

    parsed = parse_awacs_bra_en(text_lines, call_sign, unit, plane_x, plane_z)
    for item in parsed:
        key = int(item["enemy_altitude"] + item["distance"] + item["bearing"]
                  + item["enemy_heading"] + item["condition"])
        _upsert(message_dic, key, {
            "enemy_altitude": item["enemy_altitude"],
            "enemy_heading": item["enemy_heading"],
            "x": item["x"],
            "z": item["z"],
            "condition": item["condition"],
            "data_metric": unit,
            "source": source,
            "source_mode": 1,
        }, now)

    bullseye_parsed = parse_bullseye_en(text_lines, unit, bullseye_x, bullseye_z)
    for item in bullseye_parsed:
        key = int(item["bulls_enemy_altitude"] + item["x"] + item["z"])
        _upsert(bullseye_dic, key, {
            "bulls_enemy_altitude": item["bulls_enemy_altitude"],
            "x": item["x"],
            "z": item["z"],
            "enemy_heading": -1,
            "condition": 0,
            "data_metric": unit,
            "source": source,
            "source_mode": 1,
        }, now)

    return len(parsed) + len(bullseye_parsed)


# =============================================================================
# SPS / BSC 面板
# =============================================================================

def apply_sps(text_lines, metric_unit, plane_x, plane_z, message_dic,
              source="ocr", now=None):
    """SPS 面板：距离/高度单位从每行读取，配置只作强制覆盖。"""
    now = int(now if now is not None else _time.time())
    parsed = parse_sps_panel(text_lines, metric_unit)

    for item in parsed:
        # 面板每行都自带单位，且是权威来源：即使配置里选了 km/nm 也不该覆盖它，
        # 否则老配置（曾用于传统预警机）会把 53.6 NM 当成 53.6 km。
        dist_unit = item.get("distance_unit") or "nm"
        data_metric = "nm" if item.get("height_unit") == "ft" else "km"

        dist_m = convert_distance(item["distance"], dist_unit)
        key = int(item["bearing"] + dist_m + item["height"]
                  + item["speed"] + item["heading"])
        new_x, new_z = offset_coordinate(plane_x, plane_z, dist_m, item["bearing"])

        _upsert(message_dic, key, {
            "enemy_altitude": item["height"],
            "enemy_heading": item["heading"],
            "x": new_x,
            "z": new_z,
            "condition": -2,
            "speed": item["speed"],
            "callsign": item["callsign"],
            "data_metric": data_metric,
            "source": source,
            "source_mode": 2,
        }, now)

    return len(parsed)


def apply_bsc(text_lines, metric_unit, plane_x, plane_z, message_dic,
              source="ocr", now=None):
    now = int(now if now is not None else _time.time())
    unit = _panel_unit(text_lines, metric_unit)
    parsed = parse_bsc_panel(text_lines, unit)

    for item in parsed:
        dist_m = convert_distance(item["distance"], unit)
        key = int(item["bearing"] + dist_m + item["height"]
                  + item["heading"] + item["condition"])
        new_x, new_z = offset_coordinate(plane_x, plane_z, dist_m, item["bearing"])

        _upsert(message_dic, key, {
            "callsign": item["callsign"],
            "enemy_altitude": item["height"],
            "enemy_heading": item["heading"],
            "x": new_x,
            "z": new_z,
            "condition": item["condition"],
            "data_metric": unit,
            "source": source,
            "source_mode": 3,
        }, now)

    return len(parsed)
