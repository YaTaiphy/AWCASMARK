# -*- coding: utf-8 -*-
"""应用配置管理 — 单例类，使用 JSON 存储，替代原有的全局可变 Config 字典和 eval() 解析。"""

import json
import os
import random
from pathlib import Path

from log import get_logger

logger = get_logger(__name__)


class AppConfig:
    """单例配置类。

    属性化访问替代字典访问:
        config.call_sign 替代 Config["callSign"]
    在模块级创建单例实例:
        from config import config
        config.call_sign["text"] = "Springfield"
    """

    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._init_defaults()
        return cls._instance

    def _init_defaults(self):
        """初始化默认配置值。"""
        self.call_sign = {"text": "abc", "num": "9527"}
        self.bullseye = {"x": 0, "z": 0}
        self.screenshot_region = {"x": 0, "y": 0, "width": 600, "height": 400}
        self.remaining_time = 90         # 敌机标记残留时间 (秒)
        self.awacs_metric_unit = "auto"  # "auto" / "km" / "nm"；auto 仅对面板类（SPS/BSC）有效
        self.server_mode = 0             # 服务器模式 (0=传统, 1=SPS, 2=BSC)
        self.team_code = "9214"
        self.show_metrics = "km"         # 界面显示单位
        self.show_enemy = True
        self.show_friend = True
        self.show_friend_time = 180      # 友机标记残留时间 (秒)
        self.is_default_server = True
        self.server_ip = "127.0.0.1"
        self.server_port = 10386
        self.program_id = random.randint(1_000_000_000, 9_999_999_999)

        # ---- 消息来源（DCS 用户钩子 / 截图 OCR） ----
        self.message_source = "auto"     # auto / hook / ocr
        self.message_ttl = 120           # 只读取最近 N 秒的通报
        self.hook_log_path = ""          # 空 = %LOCALAPPDATA%\AWACSMARK\messages.log
        self.hook_heartbeat_timeout = 15 # 超过 N 秒没有心跳判定钩子失联

    # ---- 持久化 ----

    @staticmethod
    def config_path() -> Path:
        """配置文件路径: %LOCALAPPDATA%/AWACASConfig.json"""
        local_app_data = os.environ.get(
            "LOCALAPPDATA",
            os.path.join(os.environ["USERPROFILE"], "AppData", "Local"),
        )
        return Path(local_app_data) / "AWACASConfig.json"

    def load_from_disk(self) -> bool:
        """从磁盘加载配置，失败时保持默认值。返回是否成功加载。"""
        path = self.config_path()
        if not path.exists():
            return False
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(data, dict):
                self._apply_dict(data)
                return True
        except (json.JSONDecodeError, OSError, TypeError) as exc:
            logger.warning("读取配置文件失败，使用默认配置。%s", exc)
        return False

    def save_to_disk(self):
        """保存配置到磁盘 (JSON 格式)。"""
        path = self.config_path()
        data = {
            "call_sign": self.call_sign,
            "bullseye": self.bullseye,
            "screenshot_region": self.screenshot_region,
            "remaining_time": self.remaining_time,
            "awacs_metric_unit": self.awacs_metric_unit,
            "server_mode": self.server_mode,
            "team_code": self.team_code,
            "show_metrics": self.show_metrics,
            "show_enemy": self.show_enemy,
            "show_friend": self.show_friend,
            "show_friend_time": self.show_friend_time,
            "is_default_server": self.is_default_server,
            "server_ip": self.server_ip,
            "server_port": self.server_port,
            "program_id": self.program_id,
            "message_source": self.message_source,
            "message_ttl": self.message_ttl,
            "hook_log_path": self.hook_log_path,
            "hook_heartbeat_timeout": self.hook_heartbeat_timeout,
        }
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(data, ensure_ascii=False, indent=2),
                        encoding="utf-8")

    def _apply_dict(self, data: dict):
        """将字典中的值应用到实例属性 (仅更新已知键)。"""
        known_keys = {
            "call_sign", "bullseye", "screenshot_region", "remaining_time",
            "awacs_metric_unit", "server_mode", "team_code", "show_metrics",
            "show_enemy", "show_friend", "show_friend_time",
            "is_default_server", "server_ip", "server_port", "program_id",
            "message_source", "message_ttl", "hook_log_path",
            "hook_heartbeat_timeout",
        }
        for key, value in data.items():
            if key in known_keys and hasattr(self, key):
                setattr(self, key, value)


# =============================================================================
# 全局单例 — 替代原有的 Config 字典
# =============================================================================
config = AppConfig()
