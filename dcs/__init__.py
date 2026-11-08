# -*- coding: utf-8 -*-
"""DCS 用户钩子消息源 — 用游戏内文字回调替代截图 OCR。

模块划分：
    protocol     日志行协议（解析 / 反转义 / 心跳）
    hook_source  增量读取钩子日志（只读新增字节，不重复读）
    router       按文本特征分流到 SPS 面板 / 传统预警机
    pipeline     把解析结果写进 message_dic / bullseye_dic
"""
