# -*- coding: utf-8 -*-
"""钩子日志的增量读取。

设计要点（对应方案-第二步 §3）：
    * 只读新增字节：内部维护 offset，永不复读整文件；
    * 截断安全：文件变短（新任务/超限重写）时自动从头再来；
    * 半行安全：只处理以换行结尾的完整行，残余留在缓冲区；
    * 时间窗：启动时最多回填 120 s / 256 KB，运行中丢弃过期消息；
    * 去重：同一 kind+text 在 2 s 内只交付一次。
"""

import os
import time
from typing import List, Optional

from PySide6.QtCore import QObject, QTimer, Signal

from dcs.protocol import DcsMessage, Heartbeat, Rotation, parse_line
from log import get_logger

logger = get_logger(__name__)

POLL_INTERVAL_MS = 200
MAX_CHUNK = 64 * 1024
BACKFILL_BYTES = 256 * 1024
DEDUPE_WINDOW = 2.0


def default_log_path() -> str:
    """%LOCALAPPDATA%\\AWACSMARK\\messages.log（与 Saved Games 位置无关）。"""
    base = os.environ.get("LOCALAPPDATA") or os.path.expanduser("~")
    return os.path.join(base, "AWACSMARK", "messages.log")


class HookLogReader:
    """纯逻辑读取器，不依赖 Qt，便于单测。"""

    def __init__(self, path: str, ttl: int = 120,
                 backfill_bytes: int = BACKFILL_BYTES, clock=time.time):
        self.path = path
        self.ttl = int(ttl)
        self.backfill_bytes = int(backfill_bytes)
        self._clock = clock
        self._offset = 0
        self._buffer = b""
        self._primed = False
        self._last_beat = 0.0
        self._seen = {}          # (kind, text) -> ts
        self._head = b""         # 文件前 64 字节，用于识别重写

    # ---- 生命周期 --------------------------------------------------------

    def reset(self):
        """重新开始（新任务 / 重新开始任务）。"""
        self._offset = 0
        self._buffer = b""
        self._primed = False
        self._head = b""
        self._last_beat = 0.0
        self._seen.clear()

    def prime(self):
        """首次读取前的定位：回填最近 backfill_bytes 字节，并记住文件头。"""
        try:
            size = os.path.getsize(self.path)
        except OSError:
            size = 0
        self._offset = max(0, size - self.backfill_bytes) if self.backfill_bytes else size
        self._primed = True
        self._head = self._read_head()

    def _read_head(self) -> bytes:
        """文件前 64 字节，用来识别"被重写"（换图时钩子会截断重写）。"""
        try:
            with open(self.path, "rb") as fp:
                return fp.read(64)
        except OSError:
            return b""

    # ---- 读取 ------------------------------------------------------------

    def poll(self) -> List[DcsMessage]:
        try:
            size = os.path.getsize(self.path)
        except OSError:
            return []

        if not self._primed:
            self.prime()

        try:
            with open(self.path, "rb") as fp:
                head = fp.read(64)

                # 文件头变了 = 被截断重写过（比"文件变小"更可靠：
                # 新任务在 200 ms 内可能就长回旧 offset 之上）
                if self._head and head[:len(self._head)] != self._head:
                    logger.info("钩子日志被重写，从头读取: %s", self.path)
                    self._offset = 0
                    self._buffer = b""
                    self._seen.clear()
                self._head = head

                if size < self._offset:          # 兜底：变小但没变头
                    logger.info("钩子日志被截断，从头读取: %s", self.path)
                    self._offset = 0
                    self._buffer = b""
                    self._seen.clear()

                if size == self._offset:
                    return []

                fp.seek(self._offset)
                chunk = fp.read(min(size - self._offset, MAX_CHUNK))
        except OSError as exc:
            logger.debug("读取钩子日志失败: %s", exc)
            return []

        self._offset += len(chunk)
        self._buffer += chunk

        messages: List[DcsMessage] = []
        while b"\n" in self._buffer:
            raw, self._buffer = self._buffer.split(b"\n", 1)
            self._consume(raw.decode("utf-8", errors="replace"), messages)
        return messages

    def _consume(self, line: str, out: List[DcsMessage]):
        record = parse_line(line)
        if record is None:
            return

        now = self._clock()

        if isinstance(record, Heartbeat):
            self._last_beat = max(self._last_beat, float(record.ts))
            return

        if isinstance(record, Rotation):
            self._seen.clear()
            return

        # 时间窗：只保留最近 ttl 秒
        if record.ts and now - record.ts > self.ttl:
            return

        # 去重：同一文本 2 s 内只交付一次（防 onShowMessage/onTriggerMessage 双触发）
        key = (record.kind, record.text)
        last = self._seen.get(key)
        if last is not None and now - last < DEDUPE_WINDOW:
            return
        self._seen[key] = now

        # 清理过期的去重记录，避免字典无限增长
        if len(self._seen) > 200:
            cutoff = now - DEDUPE_WINDOW * 5
            self._seen = {k: v for k, v in self._seen.items() if v >= cutoff}

        out.append(record)

    # ---- 存活判定 --------------------------------------------------------

    @property
    def last_heartbeat(self) -> float:
        return self._last_beat

    def is_alive(self, timeout: int = 15) -> bool:
        if not self._last_beat:
            return False
        return self._clock() - self._last_beat <= max(1, int(timeout))

    # ---- 供测试用 --------------------------------------------------------

    @property
    def offset(self) -> int:
        return self._offset


class HookSource(QObject):
    """把 HookLogReader 挂到 Qt 定时器上，供主线程直接使用。

    读的是几 KB 的增量文件，单次 < 0.1 ms，不需要独立线程
    （也就没有线程关闭卡死的风险）。
    """

    message_received = Signal(object)     # DcsMessage
    alive_changed = Signal(bool)
    stalled = Signal()                    # 启动后一直没收到心跳（只发一次）

    def __init__(self, path: Optional[str] = None, ttl: int = 120,
                 heartbeat_timeout: int = 15, parent=None):
        super().__init__(parent)
        self._path = path or default_log_path()
        self._ttl = int(ttl)
        self._heartbeat_timeout = int(heartbeat_timeout)
        self._reader = HookLogReader(self._path, self._ttl)
        self._alive = False
        self._ever_alive = False
        self._stalled_notified = False
        self._started_at = 0.0

        self._timer = QTimer(self)
        self._timer.setInterval(POLL_INTERVAL_MS)
        self._timer.timeout.connect(self._poll)

    # ---- 生命周期 --------------------------------------------------------

    def start(self, resume: bool = False):
        """启动轮询。

        resume=True 时保留读取位置（停止→再开始，不重复回填旧消息）；
        resume=False 时新建 reader（应用首次启动 / 需要回填最近 120 s）。
        """
        if not resume:
            self._reader = HookLogReader(self._path, self._ttl)
        self._alive = False
        self._ever_alive = False
        self._stalled_notified = False
        self._started_at = time.time()
        self._timer.start()
        logger.info("钩子消息源启动: %s", self._path)

    def stop(self):
        self._timer.stop()
        logger.info("钩子消息源停止")

    def restart(self):
        """任务重启时清空 offset（日志可能已被钩子截断）。"""
        self._reader.reset()

    # ---- 轮询 ------------------------------------------------------------

    def _poll(self):
        try:
            messages = self._reader.poll()
        except Exception as exc:                       # 读取错误不应影响主流程
            logger.warning("钩子消息读取异常: %s", exc)
            return

        for msg in messages:
            self.message_received.emit(msg)

        alive = self._reader.is_alive(self._heartbeat_timeout)
        if alive:
            self._ever_alive = True
        if alive != self._alive:
            self._alive = alive
            self.alive_changed.emit(alive)
            logger.info("钩子心跳: %s", "在线" if alive else "失联")

        # 启动后一直没收到心跳：提示一次（钩子没装 / DCS 没重启 / 路径不可写）
        if (not self._ever_alive and not self._stalled_notified
                and time.time() - self._started_at > self._heartbeat_timeout):
            self._stalled_notified = True
            logger.warning("超过 %d 秒未收到钩子心跳：%s", self._heartbeat_timeout, self._path)
            self.stalled.emit()

    # ---- 查询 ------------------------------------------------------------

    @property
    def alive(self) -> bool:
        return self._alive

    @property
    def path(self) -> str:
        return self._path
