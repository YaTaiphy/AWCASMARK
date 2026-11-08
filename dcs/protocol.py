# -*- coding: utf-8 -*-
"""钩子日志的行协议。

写入端是 Lua 钩子（tools/dcs_hook/awacs_hook.lua），每行一条记录：

    M<TAB><epoch><TAB><trigger|radio|command|chat><TAB><escaped text>
    H<TAB><epoch><TAB><model_time>
    R                                       （日志因超限被截断）

转义规则（只处理三个字符，避免把 UTF-8 中文搞坏）：
    \\  ->  \\\\
    换行 -> \\n
    制表符 -> \\t
"""

from dataclasses import dataclass
from typing import Optional, Union

KIND_TRIGGER = "trigger"
KIND_RADIO = "radio"
KIND_COMMAND = "command"
KIND_CHAT = "chat"

_ESCAPES = {"n": "\n", "t": "\t", "\\": "\\"}


@dataclass(frozen=True)
class DcsMessage:
    """一条来自游戏内文字回调的消息。"""

    ts: int          # epoch 秒（写入端时间）
    kind: str        # trigger / radio / command / chat
    text: str        # 原始文本（已反转义，保留换行）


@dataclass(frozen=True)
class Heartbeat:
    """钩子存活信号。"""

    ts: int


@dataclass(frozen=True)
class Rotation:
    """日志被写入端主动截断。"""


def escape(text: str) -> str:
    """与 Lua 写入端保持一致的转义（供测试与工具使用）。"""
    return (str(text)
            .replace("\\", "\\\\")
            .replace("\n", "\\n")
            .replace("\t", "\\t"))


def unescape(text: str) -> str:
    """反转义；遇到未知转义保持原样，不丢字符。"""
    if "\\" not in text:
        return text
    out = []
    i = 0
    n = len(text)
    while i < n:
        ch = text[i]
        if ch == "\\" and i + 1 < n:
            nxt = text[i + 1]
            out.append(_ESCAPES.get(nxt, nxt))
            i += 2
        else:
            out.append(ch)
            i += 1
    return "".join(out)


def _to_int(value: str) -> Optional[int]:
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return None


def parse_line(line: str) -> Optional[Union[DcsMessage, Heartbeat, Rotation]]:
    """解析一行；无法识别的行返回 None（忽略，不影响其它消息）。"""
    line = line.rstrip("\r\n")
    if not line:
        return None

    parts = line.split("\t")
    tag = parts[0]

    if tag == "M" and len(parts) >= 4:
        ts = _to_int(parts[1])
        if ts is None:
            return None
        kind = parts[2].strip() or KIND_TRIGGER
        # 文本里若有未转义的制表符，后面几段会被拆开，这里拼回去
        raw_text = "\t".join(parts[3:])
        return DcsMessage(ts=ts, kind=kind, text=unescape(raw_text))

    if tag == "H" and len(parts) >= 2:
        ts = _to_int(parts[1])
        if ts is None:
            return None
        return Heartbeat(ts=ts)

    if tag == "R":
        return Rotation()

    return None
