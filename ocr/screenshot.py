# -*- coding: utf-8 -*-
"""屏幕截图工具。

注意：`mss()` 每次创建都会初始化一次 DXGI/显示设备，400 ms 一次的
创建-销毁在长时间运行后会累积显存与句柄碎片，甚至拖死 UI 线程。
因此这里复用单个实例，只在程序退出时释放。
"""

from threading import Lock

from PIL import Image
from mss import mss

_lock = Lock()
_sct = None


def take_screenshot(x: int, y: int, width: int, height: int) -> Image.Image:
    """使用 mss 截取屏幕指定区域，返回 PIL Image (RGB)。"""
    global _sct
    region = {"top": y, "left": x, "width": width, "height": height}
    with _lock:
        if _sct is None:
            _sct = mss()
        shot = _sct.grab(region)
    return Image.frombytes("RGB", (shot.width, shot.height), shot.rgb)


def close_screenshot():
    """释放 mss 实例（程序退出时调用）。"""
    global _sct
    with _lock:
        if _sct is not None:
            try:
                _sct.close()
            except Exception:
                pass
            _sct = None
