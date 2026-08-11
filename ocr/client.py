# -*- coding: utf-8 -*-
"""OCR 客户端 — 统一远程 OCR 接口，整合截图→上传→解析→去重全流程。"""

import time
from typing import Optional

from PIL import Image

from config import config
from network.http_client import upload_image_for_ocr
from ocr.parser import (
    parse_awacs_bra, parse_bullseye, parse_sps_panel, parse_bsc_panel,
    parse_awacs_bra_en, parse_bullseye_en,
    convert_distance,
)
from constants import SERVER_MODE_AWACS, SERVER_MODE_SPS, SERVER_MODE_BSC, SERVER_MODE_AWACS_EN
from log import get_logger
from utils import offset_coordinate

logger = get_logger(__name__)


# =============================================================================
# 过期消息清理
# =============================================================================

def _purge_expired(message_dic: dict, max_age_seconds: int):
    """移除超过 max_age_seconds 秒的旧消息。"""
    now = int(time.time())
    to_delete = [k for k, v in message_dic.items() if now - v["timeStamp"] > max_age_seconds]
    for k in to_delete:
        del message_dic[k]


# =============================================================================
# 统一的 OCR 识别入口
# =============================================================================

def process_screenshots(
    images: list[Image.Image],
    server_ip: str,
    server_port: int,
    call_sign: dict,
    message_dic: dict,
    bullseye_dic: dict,
    plane_x: float,
    plane_z: float,
    metric_unit: str,
    bullseye_x: float,
    bullseye_z: float,
) -> tuple[dict, dict]:
    """对截图列表执行 OCR 并返回更新后的 message_dic 和 bullseye_dic。

    该函数是原 get_enemy_bearing_OCR_flask 的重构版本。
    """
    # 清理过期消息
    _purge_expired(message_dic, config.remaining_time)
    _purge_expired(bullseye_dic, config.remaining_time)

    start_time = time.time()

    for img in images:
        status, text_lines = upload_image_for_ocr(img, server_ip, server_port,
                                                   config.server_mode)
        if status != 200 or not text_lines:
            if status != 200:
                logger.debug("OCR 上传失败 status=%s", status)
            continue

        logger.info("OCR 识别到 %d 行文本, mode=%s", len(text_lines), config.server_mode)
        for i, tl in enumerate(text_lines):
            logger.debug("  OCR[%d]: %s", i, tl)

        mode = config.server_mode

        if mode == SERVER_MODE_AWACS:
            _process_awacs(text_lines, call_sign, metric_unit, plane_x, plane_z,
                           bullseye_x, bullseye_z, message_dic, bullseye_dic)
        elif mode == SERVER_MODE_AWACS_EN:
            _process_awacs_en(text_lines, call_sign, metric_unit, plane_x, plane_z,
                              bullseye_x, bullseye_z, message_dic, bullseye_dic)
        elif mode == SERVER_MODE_SPS:
            _process_sps(text_lines, metric_unit, plane_x, plane_z, message_dic)
        elif mode == SERVER_MODE_BSC:
            _process_bsc(text_lines, metric_unit, plane_x, plane_z, message_dic)

        logger.info("OCR 处理完成: message_dic=%d 条, bullseye_dic=%d 条",
                     len(message_dic), len(bullseye_dic))

    logger.info("OCR 处理耗时: %.2f 秒", time.time() - start_time)
    return message_dic, bullseye_dic


def _process_awacs(text_lines, call_sign, metric_unit, plane_x, plane_z,
                   bullseye_x, bullseye_z, message_dic, bullseye_dic):
    """处理传统预警机模式。"""
    # BRA 通报
    parsed = parse_awacs_bra(text_lines, call_sign, metric_unit, plane_x, plane_z)
    now = int(time.time())
    for item in parsed:
        key = int(item["enemy_altitude"] + item["distance"] + item["bearing"]
                  + item["enemy_heading"] + item["condition"])
        if key not in message_dic:
            message_dic[key] = {
                "timeStamp": now,
                "enemy_altitude": item["enemy_altitude"],
                "enemy_heading": item["enemy_heading"],
                "x": item["x"],
                "z": item["z"],
                "condition": item["condition"],
                "times": 1,
            }
        else:
            message_dic[key]["times"] += 1

    # 牛眼通报
    bullseye_parsed = parse_bullseye(text_lines, metric_unit, bullseye_x, bullseye_z)
    for item in bullseye_parsed:
        key = int(item["bulls_enemy_altitude"] + item["x"] + item["z"])
        if key not in bullseye_dic:
            bullseye_dic[key] = {
                "timeStamp": now,
                "bulls_enemy_altitude": item["bulls_enemy_altitude"],
                "x": item["x"],
                "z": item["z"],
                "enemy_heading": -1,
                "condition": 0,
                "times": 1,
            }
        else:
            bullseye_dic[key]["times"] += 1


def _process_awacs_en(text_lines, call_sign, metric_unit, plane_x, plane_z,
                       bullseye_x, bullseye_z, message_dic, bullseye_dic):
    """处理传统预警机英文模式 — BRA + 牛眼通报。"""
    # 英文 BRA 通报
    parsed = parse_awacs_bra_en(text_lines, call_sign, metric_unit, plane_x, plane_z)
    logger.debug("_process_awacs_en: BRA 解析到 %d 个 contact (呼号=%s%s)",
                 len(parsed), call_sign.get("text", ""), call_sign.get("num", ""))
    now = int(time.time())
    for item in parsed:
        key = int(item["enemy_altitude"] + item["distance"] + item["bearing"]
                  + item["enemy_heading"] + item["condition"])
        if key not in message_dic:
            message_dic[key] = {
                "timeStamp": now,
                "enemy_altitude": item["enemy_altitude"],
                "enemy_heading": item["enemy_heading"],
                "x": item["x"],
                "z": item["z"],
                "condition": item["condition"],
                "times": 1,
            }
        else:
            message_dic[key]["times"] += 1

    # 英文牛眼通报
    bullseye_parsed = parse_bullseye_en(text_lines, metric_unit, bullseye_x, bullseye_z)
    for item in bullseye_parsed:
        key = int(item["bulls_enemy_altitude"] + item["x"] + item["z"])
        if key not in bullseye_dic:
            bullseye_dic[key] = {
                "timeStamp": now,
                "bulls_enemy_altitude": item["bulls_enemy_altitude"],
                "x": item["x"],
                "z": item["z"],
                "enemy_heading": -1,
                "condition": 0,
                "times": 1,
            }
        else:
            bullseye_dic[key]["times"] += 1


def _process_sps(text_lines, metric_unit, plane_x, plane_z, message_dic):
    """处理 SPS 面板模式。"""
    parsed = parse_sps_panel(text_lines, metric_unit)
    now = int(time.time())
    for item in parsed:
        dist_m = convert_distance(item["distance"], metric_unit)
        key = int(item["bearing"] + dist_m + item["height"] + item["speed"]
                  + item["heading"])
        if key not in message_dic:
            new_x, new_z = offset_coordinate(plane_x, plane_z, dist_m, item["bearing"])
            message_dic[key] = {
                "timeStamp": now,
                "enemy_altitude": item["height"],
                "enemy_heading": item["heading"],
                "x": new_x,
                "z": new_z,
                "condition": -2,
                "times": 2,
                "speed": item["speed"],
                "callsign": item["callsign"],
            }
        else:
            message_dic[key]["times"] += 1


def _process_bsc(text_lines, metric_unit, plane_x, plane_z, message_dic):
    """处理 BSC 面板模式。"""
    parsed = parse_bsc_panel(text_lines, metric_unit)
    now = int(time.time())
    for item in parsed:
        dist_m = convert_distance(item["distance"], metric_unit)
        key = int(item["bearing"] + dist_m + item["height"]
                  + item["heading"] + item["condition"])
        if key not in message_dic:
            new_x, new_z = offset_coordinate(plane_x, plane_z, dist_m, item["bearing"])
            message_dic[key] = {
                "timeStamp": now,
                "callsign": item["callsign"],
                "enemy_altitude": item["height"],
                "enemy_heading": item["heading"],
                "x": new_x,
                "z": new_z,
                "condition": item["condition"],
                "times": 1,
            }
        else:
            message_dic[key]["times"] += 1
