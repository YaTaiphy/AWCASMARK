# -*- coding: utf-8 -*-
"""AWACSMARK 入口 — DCS World 预警机标记辅助工具。

重构后的精简入口：仅负责创建 QApplication 和主窗口。
所有业务逻辑分布在 ui/, radar/, ocr/, network/, worker/ 包中。
"""

import sys
from pathlib import Path

# 确保工作目录为项目根目录 (替代原有的 os.chdir 副作用)
import os as _os
_os.chdir(Path(__file__).parent)

from PySide6.QtWidgets import QApplication
from ui.main_window import MainWindow

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())
