# -*- coding: utf-8 -*-
"""OCR 工作线程 — 可复用的 QThread Worker，替代 remoteOCR.py 每次重建的模式。"""

from PySide6.QtCore import QObject, Signal, Slot

from config import config
from log import get_logger
from ocr.client import process_screenshots

logger = get_logger(__name__)


class OCRWorker(QObject):
    """持久化 OCR 工作线程。

    通过 data_received 信号返回 (message_dic, bullseye_dic) 元组。
    每次 submit() 设置本轮参数，run() 执行后 emit 结果。
    """
    data_received = Signal(object)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._running = False
        self._screenshots = []
        self._call_sign = None
        self._message_dic = {}
        self._bullseye_dic = {}
        self._plane_x = 0.0
        self._plane_z = 0.0
        self._metric_unit = "km"
        self._bullseye_x = 0.0
        self._bullseye_z = 0.0
        self._server_ip = "127.0.0.1"
        self._server_port = 10386

    def configure(self, screenshots: list, call_sign: dict,
                  message_dic: dict, bullseye_dic: dict,
                  plane_data: dict, bullseye: dict):
        """设置本轮 OCR 参数（由主线程在定时器回调中调用）。"""
        self._screenshots = list(screenshots)  # 拷贝
        self._call_sign = dict(call_sign)
        self._message_dic = dict(message_dic)
        self._bullseye_dic = dict(bullseye_dic)
        self._plane_x = plane_data.get("x", 0)
        self._plane_z = plane_data.get("z", 0)
        self._metric_unit = config.awacs_metric_unit
        self._bullseye_x = bullseye.get("x", 0)
        self._bullseye_z = bullseye.get("z", 0)
        self._server_ip = config.server_ip
        self._server_port = config.server_port

    @Slot()
    def run(self):
        """执行 OCR 识别并 emit 结果（在 QThread 中调用）。

        通过 QMetaObject.invokeMethod + QueuedConnection 调度，
        确保本方法在 OCR 专用线程中运行，不阻塞主线程 UI。
        """
        # 本地拷贝，避免与主线程 configure() 竞争
        screenshots = self._screenshots
        call_sign = self._call_sign
        message_dic = self._message_dic
        bullseye_dic = self._bullseye_dic
        plane_x = self._plane_x
        plane_z = self._plane_z
        metric_unit = self._metric_unit
        bullseye_x = self._bullseye_x
        bullseye_z = self._bullseye_z
        server_ip = self._server_ip
        server_port = self._server_port

        self._running = True
        try:
            result = process_screenshots(
                images=screenshots,
                server_ip=server_ip,
                server_port=server_port,
                call_sign=call_sign,
                message_dic=message_dic,
                bullseye_dic=bullseye_dic,
                plane_x=plane_x,
                plane_z=plane_z,
                metric_unit=metric_unit,
                bullseye_x=bullseye_x,
                bullseye_z=bullseye_z,
            )
            self.data_received.emit(result)
        except Exception as exc:
            logger.error("OCR Worker 执行错误: %s", exc)
            self.data_received.emit((message_dic, bullseye_dic))
        finally:
            self._running = False

    def stop(self):
        """标记停止（当前正在执行的 run 会自然完成）。"""
        self._running = False
