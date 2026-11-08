# -*- coding: utf-8 -*-
"""OCR 客户端 — 截图 → 上传 → 解析 → 去重。

解析与写入逻辑已移到 dcs/pipeline.py，与 DCS 钩子路径共用；
本模块只负责"把远程 OCR 的文本交给对应的解析器"。
"""

import time

from PIL import Image

from config import config
from constants import (
    SERVER_MODE_AWACS,
    SERVER_MODE_AWACS_EN,
    SERVER_MODE_BSC,
    SERVER_MODE_SPS,
)
from dcs import pipeline
from log import get_logger
from network.http_client import upload_image_for_ocr

logger = get_logger(__name__)


def process_screenshots(
    images: list,
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
) -> tuple:
    """对截图列表执行 OCR 并返回更新后的 message_dic 和 bullseye_dic。"""
    # 清理过期消息
    pipeline.purge_expired(message_dic, config.remaining_time)
    pipeline.purge_expired(bullseye_dic, config.remaining_time)

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

        _dispatch(text_lines, config.server_mode, call_sign, metric_unit,
                  plane_x, plane_z, bullseye_x, bullseye_z,
                  message_dic, bullseye_dic)

        logger.info("OCR 处理完成: message_dic=%d 条, bullseye_dic=%d 条",
                    len(message_dic), len(bullseye_dic))

    logger.info("OCR 处理耗时: %.2f 秒", time.time() - start_time)
    return message_dic, bullseye_dic


def _dispatch(text_lines, mode, call_sign, metric_unit, plane_x, plane_z,
              bullseye_x, bullseye_z, message_dic, bullseye_dic):
    """按 server_mode 交给对应解析器（与钩子路径共用 pipeline）。"""
    if mode == SERVER_MODE_AWACS:
        pipeline.apply_awacs(text_lines, call_sign, metric_unit, plane_x, plane_z,
                             bullseye_x, bullseye_z, message_dic, bullseye_dic,
                             source="ocr")
    elif mode == SERVER_MODE_AWACS_EN:
        pipeline.apply_awacs_en(text_lines, call_sign, metric_unit, plane_x, plane_z,
                                bullseye_x, bullseye_z, message_dic, bullseye_dic,
                                source="ocr")
    elif mode == SERVER_MODE_SPS:
        pipeline.apply_sps(text_lines, metric_unit, plane_x, plane_z,
                           message_dic, source="ocr")
    elif mode == SERVER_MODE_BSC:
        pipeline.apply_bsc(text_lines, metric_unit, plane_x, plane_z,
                           message_dic, source="ocr")
