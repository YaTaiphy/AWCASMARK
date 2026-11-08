# -*- coding: utf-8 -*-
"""UDP Socket 监听 — 接收 DCS World 导出的本机飞行数据。"""

import socket
from PySide6.QtCore import QObject, Signal

from constants import UDP_LISTEN_HOST, UDP_LISTEN_PORT, UDP_BUFFER_SIZE
from log import get_logger

logger = get_logger(__name__)


class SocketWorker(QObject):
    """监听本地 UDP 端口接收 DCS 飞行数据。

    数据格式 (14 字段):
      timestamp,x,y,z,heading,pitch,bank,lat,long,height,altBar,altRad,trueAirSpeed,indicatedAirSpeed
    向后兼容旧格式 (10 字段):
      timestamp,x,y,z,heading,pitch,bank,lat,long,height
    """
    data_received = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._running = False
        self._sock = None

    def start_listening(self):
        """启动 UDP 监听循环 (在 QThread 中调用)。"""
        self._running = True
        try:
            self._sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            self._sock.bind((UDP_LISTEN_HOST, UDP_LISTEN_PORT))
            self._sock.settimeout(0.5)  # 超时以便检查 _running 标志

            while self._running:
                try:
                    data, _addr = self._sock.recvfrom(UDP_BUFFER_SIZE)
                    message = data.decode("utf-8").strip()
                    self.data_received.emit(message)
                except socket.timeout:
                    continue  # 超时 → 再次检查 _running
                except BlockingIOError:
                    continue
        except OSError as exc:
            # _running=False 表示是主动停止（stop_listening 关闭了 socket），
            # 此时 recvfrom 抛出的 WSAENOTSOCK (10038) 属于正常行为，不报错。
            if self._running:
                logger.error("UDP 监听错误: %s", exc)
            else:
                logger.debug("UDP 监听已停止 (socket 正常关闭)")
        finally:
            if self._sock:
                try:
                    self._sock.close()
                except OSError:
                    pass
            self._sock = None
            self._running = False

    def stop_listening(self):
        """停止监听（可跨线程安全调用）。"""
        self._running = False
        # 关闭 socket 以中断阻塞中的 recvfrom，触发线程退出
        sock = self._sock  # 避免竞态：先取引用
        if sock is not None:
            try:
                sock.close()
            except OSError:
                pass
