# -*- coding: utf-8 -*-
"""QFont 缓存。

渲染每帧都会给每个标记设置字体，原来每次 `QFont()` + `setPointSize`
会高频分配对象；字体是只读的，按 (字号, 粗体) 缓存即可。
"""

from PySide6.QtGui import QFont

_cache = {}


def get_font(point_size: int, bold: bool = False) -> QFont:
    key = (int(point_size), bool(bold))
    font = _cache.get(key)
    if font is None:
        font = QFont()
        font.setPointSize(key[0])
        font.setBold(key[1])
        _cache[key] = font
    return font
