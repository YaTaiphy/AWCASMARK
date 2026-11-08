# -*- coding: utf-8 -*-
"""消息解析测试 — 使用 dcs.parser 模块验证 SPS/BSC/AWACS 解析正确性。"""

from dcs.parser import parse_sps_panel, parse_bsc_panel, parse_awacs_bra
from config import config


# =============================================================================
# SPS 面板格式测试数据
# =============================================================================
# 格式: "机型 编号 方位 距离NM 高度ft 速度Knts 航向 Hot/Cold/Flank"

SPS_TEST_MESSAGES = [
    "MiG-29 Fulcrum 191 141,1 NM 8,000 ft 649 Knts 348 Hot",
    "MiG-295 193 142.9 NM 6,000 ft 544 Knts 013 Hot",
    "IL-76MD 211 195.3 NM 20,000 ft 399 Knts 023 Hot",
    "IL-76MD 209 258.8 NM 20,000 ft 399 Knts 023 Hot",
    "F-16C_50  194 125.2 NM 5,000 ft 643 Knts 252 Flank Right",
    "Mig-29 Fulcrum 194 137.2 NM",
    "~YSUNC3FRS: 6530015778,469 192 Cold",
    "Mig-29 Fulcrum 174 99.6 NM 2,000 ft 604 Knts 351 Hot",
    "Mig-29 Fulcrum 194 122.2 NM 7,000 ft 661 Knts 025 Hot",
    "F-16C 50 193 124.1 NM 5,000 ft 621 Knts 009 Hot",
    "F-16C_50 192 142.8 NM 14,000 ft 657 Knts 004 Hot",
    "IL-76MD 209 238.9 NM 20,000 ft 399 Knts 023 Hot",
    "FA-18C hornet 287 159.7 Km 7,000 m 935 Km/h 090 Hot",
]


def test_sps_parsing():
    """测试 SPS 面板消息解析。"""
    print("=== SPS 面板解析测试 ===")
    for msg in SPS_TEST_MESSAGES:
        result = parse_sps_panel([msg], config.awacs_metric_unit)
        if result:
            for r in result:
                print(f"  OK: callsign={r['callsign']}, bearing={r['bearing']}, "
                      f"distance={r['distance']}, heading={r['heading']}, "
                      f"speed=M{r['speed']:.4f}")
        else:
            print(f"  SKIP (不完整消息): {msg.strip()[:60]}...")


if __name__ == "__main__":
    test_sps_parsing()
