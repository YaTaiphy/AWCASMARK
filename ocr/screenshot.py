# -*- coding: utf-8 -*-
"""屏幕截图工具。"""

from PIL import Image
from mss import mss


def take_screenshot(x: int, y: int, width: int, height: int) -> Image.Image:
    """使用 mss 截取屏幕指定区域，返回 PIL Image (RGB)。"""
    with mss() as sct:
        region = {"top": y, "left": x, "width": width, "height": height}
        screenshot = sct.grab(region)
        return Image.frombytes("RGB", (screenshot.width, screenshot.height), screenshot.rgb)
