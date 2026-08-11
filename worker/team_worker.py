# -*- coding: utf-8 -*-
"""队友同步工作线程 — 可复用的 QThread Worker，替代 remoteTeam.py。"""

from PySide6.QtCore import QObject, Signal, Slot

from config import config
from log import get_logger
from network.http_client import sync_team_data

logger = get_logger(__name__)


class TeamWorker(QObject):
    """持久化队友同步工作线程。

    通过 data_received 信号返回队友列表 (list[dict] 或 None)。
    失败后退避：连续失败后跳过若干周期，避免持续阻塞导致 UI 卡顿。
    """
    data_received = Signal(object)

    # 退避参数
    _BACKOFF_CYCLES = 5   # 连续失败后跳过 5 个周期 (~20s @4s 间隔)
    _MAX_SKIP = 15        # 最大跳过周期数

    def __init__(self, parent=None):
        super().__init__(parent)
        self._running = False
        self._plane_data = {}
        self._server_ip = "127.0.0.1"
        self._server_port = 10386
        self._fail_count = 0
        self._skip_remaining = 0

    def configure(self, plane_data: dict):
        """设置本轮参数（由主线程在定时器回调中调用）。"""
        self._plane_data = dict(plane_data)
        self._server_ip = config.server_ip
        self._server_port = config.server_port

    @Slot()
    def run(self):
        """执行队友同步并 emit 结果（在 QThread 中调用）。

        连续失败后退避，避免每秒尝试连接不可达的服务器造成卡顿。

        通过 QMetaObject.invokeMethod + QueuedConnection 调度，
        确保本方法在 Team 专用线程中运行，不阻塞主线程 UI。
        """
        # 退避期间直接跳过
        if self._skip_remaining > 0:
            self._skip_remaining -= 1
            logger.debug("Team 同步退避中… 剩余跳过 %d 次", self._skip_remaining)
            return

        # 本地拷贝，避免与主线程 configure() 竞争
        plane_data = dict(self._plane_data)
        server_ip = self._server_ip
        server_port = self._server_port

        self._running = True
        try:
            status, team_data = sync_team_data(
                plane_data, server_ip, server_port
            )
            if status == 200:
                self._fail_count = 0
                self._skip_remaining = 0
                self.data_received.emit(team_data)
            else:
                self._fail_count += 1
                if self._fail_count >= 3:
                    self._skip_remaining = min(
                        self._BACKOFF_CYCLES * (self._fail_count - 2),
                        self._MAX_SKIP,
                    )
                    logger.debug("Team 同步连续失败 %d 次，退避 %d 个周期",
                                 self._fail_count, self._skip_remaining)
                self.data_received.emit(None)
        except Exception as exc:
            logger.error("Team Worker 执行错误: %s", exc)
            self._fail_count += 1
            self.data_received.emit(None)
        finally:
            self._running = False

    def stop(self):
        """标记停止。"""
        self._running = False
        self._fail_count = 0
        self._skip_remaining = 0
