# -*- coding: utf-8 -*-
"""统一日志模块 — 基于 Python logging，同时输出到控制台和文件。

用法:
    from log import get_logger
    logger = get_logger(__name__)
    logger.info("消息")
    logger.warning("警告")
    logger.error("错误")

日志文件: ./logs/app.log (自动轮转，单文件最大 1 MB，保留 3 个备份)
"""

import logging
import os
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path

# =============================================================================
# 默认配置
# =============================================================================

_LOG_DIR = Path(__file__).parent / "logs"
_LOG_FILE = _LOG_DIR / "app.log"
_MAX_BYTES = 1 * 1024 * 1024   # 1 MB
_BACKUP_COUNT = 3              # 保留最近 3 个备份

# 日志格式: "2024-01-01 12:00:00 [INFO] [module.name] message"
_FORMAT = "%(asctime)s [%(levelname)-7s] [%(name)s] %(message)s"
_DATE_FORMAT = "%Y-%m-%d %H:%M:%S"

_initialized = False


def _init_logging():
    """初始化日志系统 — 仅执行一次。"""
    global _initialized
    if _initialized:
        return

    # 确保日志目录存在
    _LOG_DIR.mkdir(parents=True, exist_ok=True)

    # 根 logger 配置
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.DEBUG)

    # 格式器
    formatter = logging.Formatter(_FORMAT, datefmt=_DATE_FORMAT)

    # ---- 文件处理器 (DEBUG 级别) ----
    file_handler = RotatingFileHandler(
        _LOG_FILE, maxBytes=_MAX_BYTES, backupCount=_BACKUP_COUNT,
        encoding="utf-8",
    )
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(formatter)
    root_logger.addHandler(file_handler)

    # ---- 控制台处理器 (INFO 级别) ----
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(formatter)
    root_logger.addHandler(console_handler)

    _initialized = True


def get_logger(name: str) -> logging.Logger:
    """获取指定名称的 Logger 实例。

    Args:
        name: 通常传 __name__，会在日志中显示为 "dcs.parser" 等缩写

    Returns:
        配置好的 logging.Logger 实例
    """
    _init_logging()

    # 裁剪名称：将顶层包名前缀移除，使日志更简洁
    # 例如 "dcs.parser" 保持不变，"__main__" → "main"
    if name == "__main__":
        name = "main"

    return logging.getLogger(name)
