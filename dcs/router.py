# -*- coding: utf-8 -*-
"""按文本特征分流（不依赖 server_mode 配置）。

依据实机验证（2026-11）：
    onTriggerMessage → "Contention EWR | Picture Report" + TYPE/BRG/RNG 表头 → SPS 面板
    onRadioMessage   → "预警机 (Overlord1-1): 128, ... 351 方位, 距离 210, 高度 11000" → BRA
                       "... 战场信息: ... 首要敌方机队 相对"靶眼"位置: ..." → 牛眼
"""

import time as _time
from dataclasses import dataclass, field

from dcs import pipeline
from dcs.protocol import DcsMessage, KIND_RADIO, KIND_TRIGGER
from log import get_logger

logger = get_logger(__name__)

# 玩家自己发出的请求（"玩家: Overlord1-1, 128, 请求战场信息"），不能当敌情
_PLAYER_PREFIXES = ("玩家", "player")

# 路由结果，便于日志与测试
MODE_SPS = "sps"
MODE_AWACS = "awacs"
MODE_AWACS_EN = "awacs_en"
MODE_BSC = "bsc"
MODE_IGNORED = "ignored"


@dataclass
class RouteContext:
    """路由/写入所需的本机与配置信息（每次消息到达时由主窗口填充）。"""

    call_sign: dict
    metric_unit: str                 # "auto" / "km" / "nm"
    plane_x: float
    plane_z: float
    bullseye_x: float
    bullseye_z: float
    message_dic: dict = field(default_factory=dict)
    bullseye_dic: dict = field(default_factory=dict)
    source: str = "hook"             # "hook" / "ocr"
    now: int = 0


def split_lines(text: str) -> list:
    return [line.strip() for line in text.splitlines() if line.strip()]


def is_player_echo(text: str) -> bool:
    stripped = text.lstrip()
    return any(stripped.lower().startswith(p) for p in _PLAYER_PREFIXES)


def looks_like_sps_panel(lines: list) -> bool:
    head = "\n".join(lines[:4]).upper()
    if "TYPE" in head and "BRG" in head:
        return True

    # 没有表头时的兜底：多行带 NM/ft 距离高度 + 接敌状态词
    hits = [l for l in lines
            if ("nm" in l.lower() or "km" in l.lower())
            and ("ft" in l.lower() or "m " in l.lower())]
    if len(hits) < 2:
        return False
    return any(("hot" in l.lower() or "cold" in l.lower()
                or "flank" in l.lower()) for l in lines)


def looks_like_awacs(lines: list) -> bool:
    if any("方位" in l and "距离" in l for l in lines):
        return True
    lower = "\n".join(lines).lower()
    return " for " in lower and "altitude" in lower


def route(msg: DcsMessage, ctx: RouteContext) -> str:
    """把一条消息写进 ctx 的字典，返回使用的模式名。"""
    if is_player_echo(msg.text):
        return MODE_IGNORED

    lines = split_lines(msg.text)
    if not lines:
        return MODE_IGNORED

    now = ctx.now or int(_time.time())

    # 面板类：只可能出现在触发器文字里
    if msg.kind == KIND_TRIGGER and looks_like_sps_panel(lines):
        count = pipeline.apply_sps(lines, ctx.metric_unit, ctx.plane_x,
                                   ctx.plane_z, ctx.message_dic,
                                   source=ctx.source, now=now)
        return MODE_SPS if count else MODE_IGNORED

    # BRA / 牛眼：正常走无线电；部分服务器用 outText 播报，所以触发器也认
    if looks_like_awacs(lines):
        english = any(" for " in l.lower() for l in lines)
        if english:
            count = pipeline.apply_awacs_en(
                lines, ctx.call_sign, ctx.metric_unit, ctx.plane_x, ctx.plane_z,
                ctx.bullseye_x, ctx.bullseye_z, ctx.message_dic, ctx.bullseye_dic,
                source=ctx.source, now=now)
            return MODE_AWACS_EN if count else MODE_IGNORED

        count = pipeline.apply_awacs(
            lines, ctx.call_sign, ctx.metric_unit, ctx.plane_x, ctx.plane_z,
            ctx.bullseye_x, ctx.bullseye_z, ctx.message_dic, ctx.bullseye_dic,
            source=ctx.source, now=now)
        return MODE_AWACS if count else MODE_IGNORED

    # 其余（公告、ATC、无线电菜单、聊天）一律忽略
    return MODE_IGNORED
