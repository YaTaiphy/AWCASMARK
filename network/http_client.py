# -*- coding: utf-8 -*-
"""HTTP 通信 — 远程 OCR 上传、队友同步、服务器健康检查。"""

import json
import http.client
import base64
import io
import time
from typing import Optional

from PIL import Image

from config import config
from constants import HTTP_TIMEOUT, HTTP_HEALTH_TIMEOUT
from log import get_logger

logger = get_logger(__name__)


# =============================================================================
# 图像编码
# =============================================================================

def image_to_base64(image: Image.Image) -> str:
    """将 PIL Image 编码为 base64 字符串。"""
    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    buffer.seek(0)
    return base64.b64encode(buffer.read()).decode("utf-8")


# =============================================================================
# 服务器健康检查
# =============================================================================

def check_server_health(host: str, port: int, timeout: int = HTTP_HEALTH_TIMEOUT) -> bool:
    """检查远程服务器是否可达。"""
    conn = None
    try:
        conn = http.client.HTTPConnection(host, port, timeout=timeout)
        conn.request("GET", "/health")
        response = conn.getresponse()
        return response.status == 200
    except Exception as exc:
        logger.warning("无法连接到服务器 %s:%s - %s", host, port, exc)
        return False
    finally:
        if conn:
            conn.close()


# =============================================================================
# OCR 图像上传
# =============================================================================

def upload_image_for_ocr(image: Image.Image, server_ip: str, server_port: int,
                         mode: int) -> tuple[int, Optional[list]]:
    """发送截图到远程 OCR 服务器并返回识别文本。

    Returns:
        (status_code, text_list) — status_code==200 时 text_list 有效，否则 (error_code, None)
    """
    # 快速 TCP 预检：1 秒内连不上就直接放弃，避免 TCP connect 阻塞 20+ 秒
    import socket as _socket
    try:
        sock = _socket.socket(_socket.AF_INET, _socket.SOCK_STREAM)
        sock.settimeout(1.0)
        sock.connect((server_ip, server_port))
        sock.close()
    except OSError:
        return -1, None

    conn = None
    try:
        conn = http.client.HTTPConnection(server_ip, server_port, timeout=HTTP_TIMEOUT)
        payload = {
            "mode": mode,
            "image": image_to_base64(image),
            "metadata": {
                "size": f"{image.width}x{image.height}",
                "mode": image.mode,
            },
        }
        json_data = json.dumps(payload)
        headers = {
            "Content-Type": "application/json",
            "Content-Length": str(len(json_data)),
        }
        conn.request("POST", "/upload", json_data, headers)
        response = conn.getresponse()
        response_data = response.read().decode("utf-8")
        result = json.loads(response_data)

        if response.status == 200 and "text" in result:
            return 200, result["text"]
        else:
            logger.warning("OCR 上传失败，状态码: %s", response.status)
            return response.status, None
    except Exception as exc:
        logger.error("OCR 上传错误: %s", exc)
        return -1, None
    finally:
        if conn:
            conn.close()


# =============================================================================
# 队友位置同步
# =============================================================================

def sync_team_data(plane_data: dict, server_ip: str, server_port: int) -> tuple[int, Optional[list]]:
    """上报本机位置并获取队友列表。

    Returns:
        (status_code, team_list) — 已去除自身数据的队友列表
    """
    # 快速 TCP 预检：1 秒内连不上就直接放弃，避免阻塞卡顿
    import socket as _socket
    try:
        sock = _socket.socket(_socket.AF_INET, _socket.SOCK_STREAM)
        sock.settimeout(1.5)
        sock.connect((server_ip, server_port))
        sock.close()
    except OSError:
        return -1, None

    conn = None
    try:
        conn = http.client.HTTPConnection(server_ip, server_port, timeout=5)

        if config.call_sign["text"]:
            call_sign = config.call_sign["text"][0] + str(config.call_sign["num"])
        else:
            call_sign = str(config.call_sign["num"])

        data = {
            "teamcode": config.team_code,
            "heading": plane_data["heading"],
            "x": plane_data["x"],
            "y": plane_data["y"],
            "z": plane_data["z"],
            "timestamp": int(time.time()),
            "callSign": call_sign,
            "id": config.program_id,
        }
        json_data = json.dumps(data)
        headers = {
            "Content-type": "application/json",
            "Content-length": str(len(json_data)),
        }
        conn.request("POST", "/team", json_data, headers)
        response = conn.getresponse()

        if response.status == 200:
            team_data = response.read().decode("utf-8")
            results = json.loads(team_data)
            # 去除自身
            results = [mate for mate in results if mate.get("id") != config.program_id]
            return 200, results
        else:
            logger.warning("队友同步失败，状态码: %s", response.status)
            return response.status, None
    except Exception as exc:
        logger.error("队友同步错误: %s", exc)
        return -1, None
    finally:
        if conn:
            conn.close()
