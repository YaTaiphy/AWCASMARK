# -*- coding: utf-8 -*-
"""网络通信 — 队友位置同步与服务器可达性检查。

OCR 上传相关代码已随截图链路一起移除（消息改为从 DCS 钩子读取）。
"""

import json
import socket
import time
from typing import Optional

from config import config
from log import get_logger

logger = get_logger(__name__)


# =============================================================================
# 服务器可达性
# =============================================================================

def check_server_health(host: str, port: int, timeout: float = 3.0) -> bool:
    """TCP 连接检查（只判断端口是否可达，不再依赖 OCR 服务的 /health）。"""
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except OSError as exc:
        logger.warning("无法连接到服务器 %s:%s - %s", host, port, exc)
        return False


# =============================================================================
# 队友位置同步
# =============================================================================

def sync_team_data(plane_data: dict, server_ip: str, server_port: int) -> tuple:
    """上报本机位置并获取队友列表。

    Returns:
        (status_code, team_list) — 已去除自身数据的队友列表
    """
    # 快速 TCP 预检：1.5 秒内连不上就直接放弃，避免阻塞卡顿
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(1.5)
        sock.connect((server_ip, server_port))
        sock.close()
    except OSError:
        return -1, None

    import http.client

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

        logger.warning("队友同步失败，状态码: %s", response.status)
        return response.status, None
    except Exception as exc:
        logger.error("队友同步错误: %s", exc)
        return -1, None
    finally:
        if conn:
            conn.close()
