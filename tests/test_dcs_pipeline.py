# -*- coding: utf-8 -*-
"""DCS 消息管线单测 —— 不依赖 pytest，直接运行：

    python tests/test_dcs_pipeline.py

样本全部取自 2026-11-08 实机钩子日志（onTriggerMessage / onRadioMessage）。
"""

import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dcs import pipeline                                   # noqa: E402
from dcs.hook_source import HookLogReader                  # noqa: E402
from dcs.parser import parse_awacs_bra                     # noqa: E402
from dcs.protocol import (                                 # noqa: E402
    DcsMessage, Heartbeat, Rotation, escape, parse_line, unescape,
)
from dcs.router import (                                   # noqa: E402
    MODE_AWACS, MODE_IGNORED, MODE_SPS, RouteContext, route,
)
from utils import calculate_bearing_and_distance           # noqa: E402

# ---------------------------------------------------------------------------
# 实机样本
# ---------------------------------------------------------------------------

SPS_SAMPLE = """Contention EWR | Picture Report

TYPE            BRG         RNG         ALT                  SPD            HDG         Aspect

F-16            170    53.6 NM       21,000 ft      911 Knts         348         Hot

F-14            181    55.0 NM       30,000 ft      573 Knts         350         Hot

F/A-18          170    56.8 NM        6,000 ft      678 Knts         136         Cold

F/A-18          198    57.4 NM       11,000 ft      549 Knts         276         Flank Right

F-14            171    62.2 NM        6,000 ft      543 Knts         203         Cold

F-14            172    63.5 NM       11,000 ft      637 Knts         335         Hot"""

BRA_SAMPLE = ("预警机 (Overlord1-1): 128, Overlord1-1, 敌情 (BRA), "
              "351 方位, 距离 210, 高度 11000, 尾追")

BULLSEYE_SAMPLE = """预警机 (Overlord1-1): 128, Overlord1-1, 战场信息: , 9 机队
首要敌方机队 相对"靶眼"位置: 075 方位, 距离 190, 高度 1500
次要敌方机队 相对"靶眼"位置: 118 方位, 距离 60, 高度 5000
次要敌方机队 相对"靶眼"位置: 098 方位, 距离 40, 高度 6000
次要敌方机队 相对"靶眼"位置: 102 方位, 距离 30, 高度 12000
次要敌方机队 相对"靶眼"位置: 040 方位, 距离 160, 高度 10000
次要敌方机队 相对"靶眼"位置: 117 方位, 距离 8, 高度 12000
次要敌方机队 相对"靶眼"位置: 044 方位, 距离 250, 高度 11000
次要敌方机队 相对"靶眼"位置: 265 方位, 距离 30, 高度 11000
次要敌方机队 相对"靶眼"位置: 295 方位, 距离 50, 高度 7000"""

CALL_SIGN = {"text": "", "num": "128"}

BASE_CTX = dict(
    call_sign=CALL_SIGN,
    metric_unit="auto",
    plane_x=0.0,
    plane_z=0.0,
    bullseye_x=1000.0,
    bullseye_z=2000.0,
    source="hook",
)


def make_ctx(**over):
    kwargs = dict(BASE_CTX)
    kwargs.update(over)
    kwargs.setdefault("message_dic", {})
    kwargs.setdefault("bullseye_dic", {})
    return RouteContext(**kwargs)


# ---------------------------------------------------------------------------
# 1. 行协议
# ---------------------------------------------------------------------------

def test_protocol_roundtrip():
    text = '第一行\n第二行\t带 Tab\\反斜杠'
    line = "M\t1700000000\tradio\t" + escape(text)
    record = parse_line(line)
    assert isinstance(record, DcsMessage)
    assert record.ts == 1700000000
    assert record.kind == "radio"
    assert record.text == text, record.text

    assert isinstance(parse_line("H\t1700000000\t123.4"), Heartbeat)
    assert isinstance(parse_line("R"), Rotation)
    assert parse_line("garbage") is None
    assert parse_line("") is None


def test_unescape_keeps_unknown():
    assert unescape(r"a\qb") == "aqb"


# ---------------------------------------------------------------------------
# 2. SPS 面板（onTriggerMessage）
# ---------------------------------------------------------------------------

def test_sps_panel():
    ctx = make_ctx()
    mode = route(DcsMessage(ts=0, kind="trigger", text=SPS_SAMPLE), ctx)
    assert mode == MODE_SPS, mode
    assert len(ctx.message_dic) == 6, len(ctx.message_dic)

    first = ctx.message_dic[next(iter(ctx.message_dic))]
    assert first["enemy_altitude"] == 21000
    assert first["data_metric"] == "nm"          # 面板自带 NM/ft，不依赖配置
    assert first["source"] == "hook"

    # 第一条：方位 170 / 53.6 NM
    dist, brg = calculate_bearing_and_distance(0, 0, first["x"], first["z"])
    assert abs(dist - 53.6 * 1852) < 1.0, dist
    assert abs(brg - 170) < 0.5, brg


def test_sps_unit_is_per_row():
    """面板若给 km/m，也应按行内单位换算，而不是全局配置。"""
    line = ("MiG-29          090    40.0 KM        8,000 m      900 Km/h         090         Hot")
    ctx = make_ctx()
    mode = route(DcsMessage(ts=0, kind="trigger",
                            text="TYPE BRG RNG ALT SPD HDG Aspect\n" + line), ctx)
    assert mode == MODE_SPS
    entry = ctx.message_dic[next(iter(ctx.message_dic))]
    assert entry["data_metric"] == "km"
    dist, _ = calculate_bearing_and_distance(0, 0, entry["x"], entry["z"])
    assert abs(dist - 40_000) < 1.0, dist


# ---------------------------------------------------------------------------
# 3. 传统预警机（onRadioMessage）
# ---------------------------------------------------------------------------

def test_awacs_bra():
    ctx = make_ctx()
    mode = route(DcsMessage(ts=0, kind="radio", text=BRA_SAMPLE), ctx)
    assert mode == MODE_AWACS, mode
    assert len(ctx.message_dic) == 1

    entry = ctx.message_dic[next(iter(ctx.message_dic))]
    assert entry["enemy_altitude"] == 11000
    assert entry["condition"] == -1                    # 尾追
    assert entry["data_metric"] == "km"                # auto 在传统通路回退 km
    dist, brg = calculate_bearing_and_distance(0, 0, entry["x"], entry["z"])
    assert abs(dist - 210_000) < 1.0, dist
    assert abs(brg - 351) < 0.5, brg


def test_awacs_bullseye():
    ctx = make_ctx()
    mode = route(DcsMessage(ts=0, kind="radio", text=BULLSEYE_SAMPLE), ctx)
    assert mode == MODE_AWACS, mode
    assert len(ctx.bullseye_dic) == 9, len(ctx.bullseye_dic)

    # 首要机队：075 方位 / 190 / 1500
    entry = min(ctx.bullseye_dic.values(), key=lambda e: e["bulls_enemy_altitude"])
    assert entry["bulls_enemy_altitude"] == 1500
    dist, brg = calculate_bearing_and_distance(1000, 2000, entry["x"], entry["z"])
    assert abs(dist - 190_000) < 1.0, dist
    assert abs(brg - 75) < 0.5, brg


def test_callsign_matching():
    """接收方既可能是纯数字，也可能是 'Uzi 1-1' 这类字母+数字。"""

    def radio(receiver):
        return (f"预警机 (Overlord1-1): {receiver}, Overlord1-1, 敌情 (BRA), "
                "351 方位, 距离 210, 高度 11000, 尾追")

    cases = [
        ({"text": "", "num": "128"}, "128", 1),
        ({"text": "Uzi", "num": "11"}, "Uzi 11", 1),
        ({"text": "Uzi", "num": "11"}, "Uzi 1-1", 1),
        ({"text": "Uzi", "num": "11"}, "UZI-11", 1),
        ({"text": "Uzi", "num": "11"}, "Uzi 12", 0),
        ({"text": "Uzi", "num": "1"}, "Uzi 11", 0),     # 不能因为末位相同就误匹配
        ({"text": "", "num": "128"}, "5128", 0),
        ({"text": "Uzi", "num": "11"}, "128", 0),
    ]
    for call_sign, receiver, expected in cases:
        got = len(parse_awacs_bra([radio(receiver)], call_sign, "km", 0, 0))
        assert got == expected, f"{call_sign} vs {receiver!r}: {got} != {expected}"


def test_trigger_bra_is_routed():
    """有些服务器用 outText（trigger）发 BRA，不能只认 radio。"""
    ctx = make_ctx()
    mode = route(DcsMessage(ts=0, kind="trigger", text=BRA_SAMPLE), ctx)
    assert mode == MODE_AWACS, mode
    assert len(ctx.message_dic) == 1


def test_forced_format_overrides_detection():
    """手动指定格式时只走对应解析器；解析不出就返回 ignored，不硬解。"""
    from constants import FORMAT_AWACS, FORMAT_SPS

    # 强制 SPS：面板文本正常解析
    ctx = make_ctx(format=FORMAT_SPS)
    mode = route(DcsMessage(ts=0, kind="trigger", text=SPS_SAMPLE), ctx)
    assert mode == MODE_SPS and len(ctx.message_dic) == 6

    # 强制 SPS：传统 BRA 不应被当成面板
    ctx = make_ctx(format=FORMAT_SPS)
    assert route(DcsMessage(ts=0, kind="radio", text=BRA_SAMPLE), ctx) == MODE_IGNORED
    assert not ctx.message_dic

    # 强制传统：SPS 面板不应被当成 BRA
    ctx = make_ctx(format=FORMAT_AWACS)
    assert route(DcsMessage(ts=0, kind="trigger", text=SPS_SAMPLE), ctx) == MODE_IGNORED

    # 强制传统：正常 BRA 仍然解析
    ctx = make_ctx(format=FORMAT_AWACS)
    mode = route(DcsMessage(ts=0, kind="radio", text=BRA_SAMPLE), ctx)
    assert mode == MODE_AWACS and len(ctx.message_dic) == 1


def test_config_migrates_old_server_mode():
    """老配置只有 server_mode（0..3），应迁移为 message_format。"""
    from config import AppConfig
    from constants import FORMAT_SPS

    cfg = AppConfig()
    cfg.message_format = "auto"
    cfg._apply_dict({"server_mode": 2})
    assert cfg.message_format == FORMAT_SPS
    cfg.message_format = "auto"


def test_player_echo_ignored():
    ctx = make_ctx()
    mode = route(DcsMessage(ts=0, kind="radio",
                            text="玩家: Overlord1-1, 128, 请求战场信息"), ctx)
    assert mode == MODE_IGNORED
    assert not ctx.message_dic


def test_server_notice_ignored():
    ctx = make_ctx()
    for text in ("Welcome to Contention, YATEIFEI!",
                 "Takeoff Delay Timer: 180 seconds remaining.",
                 "Suggested Mission: Cargo Intercept"):
        assert route(DcsMessage(ts=0, kind="trigger", text=text), ctx) == MODE_IGNORED


# ---------------------------------------------------------------------------
# 4. 重复播报：续命 + 重算坐标
# ---------------------------------------------------------------------------

def test_repeat_refreshes_timestamp():
    lines = [l for l in SPS_SAMPLE.splitlines() if l.strip()]
    dic = {}
    pipeline.apply_sps(lines, "auto", 0.0, 0.0, dic, source="hook", now=1000)
    key = next(iter(dic))
    assert dic[key]["times"] == 1 and dic[key]["timeStamp"] == 1000

    # 10 秒后再次播报，且本机已经移动
    pipeline.apply_sps(lines, "auto", 50_000.0, 0.0, dic, source="hook", now=1010)
    assert dic[key]["times"] == 2
    assert dic[key]["timeStamp"] == 1010, "第二次播报必须重置衰减时间"

    dist, _ = calculate_bearing_and_distance(50_000.0, 0.0, dic[key]["x"], dic[key]["z"])
    assert abs(dist - 53.6 * 1852) < 1.0, "坐标应按新本机位置重算"


def test_purge_expired():
    dic = {1: {"timeStamp": 100}, 2: {"timeStamp": 900}}
    pipeline.purge_expired(dic, 120, now=1000)
    assert list(dic) == [2]


# ---------------------------------------------------------------------------
# 5. 日志增量读取
# ---------------------------------------------------------------------------

def test_reader_incremental_and_truncate():
    fd, path = tempfile.mkstemp(suffix=".log")
    os.close(fd)
    now = [1_700_000_000.0]
    reader = HookLogReader(path, ttl=120, clock=lambda: now[0])

    with open(path, "w", encoding="utf-8") as fp:
        fp.write("M\t1700000000\ttrigger\t第一条\n")
        fp.write("M\t1700000001\tradio\t第二条\n")
        fp.write("H\t1700000001\t10.0\n")

    msgs = reader.poll()
    assert [m.text for m in msgs] == ["第一条", "第二条"]

    # 没有新增时不会重复读
    assert reader.poll() == []
    offset = reader.offset

    # 追加一条，只读新增部分
    with open(path, "a", encoding="utf-8") as fp:
        fp.write("M\t1700000002\ttrigger\t第三条\n")
    msgs = reader.poll()
    assert [m.text for m in msgs] == ["第三条"]
    assert reader.offset > offset

    # 文件被截断（新任务）→ 从头读
    with open(path, "w", encoding="utf-8") as fp:
        fp.write("M\t1700000003\ttrigger\t新任务\n")
    msgs = reader.poll()
    assert [m.text for m in msgs] == ["新任务"]

    # 半行：只有换行后才交付
    with open(path, "a", encoding="utf-8") as fp:
        fp.write("M\t1700000004\ttrigger\t半行")
    assert reader.poll() == []
    with open(path, "a", encoding="utf-8") as fp:
        fp.write("结束\n")
    assert [m.text for m in reader.poll()] == ["半行结束"]

    os.remove(path)


def test_reader_detects_rewrite_growing_file():
    """换图时钩子会截断重写；新文件可能很快又长过旧 offset，必须靠文件头识别。"""
    fd, path = tempfile.mkstemp(suffix=".log")
    os.close(fd)
    now = [1_700_000_000.0]
    reader = HookLogReader(path, ttl=120, clock=lambda: now[0])

    with open(path, "w", encoding="utf-8") as fp:
        fp.write("M\t1700000000\ttrigger\t旧任务\n")
    assert [m.text for m in reader.poll()] == ["旧任务"]

    # 重写成更长的内容（长度超过旧 offset，靠 size < offset 判断会漏）
    with open(path, "w", encoding="utf-8") as fp:
        fp.write("M\t1700000001\ttrigger\t新任务一\n")
        fp.write("M\t1700000002\ttrigger\t新任务二\n")

    assert [m.text for m in reader.poll()] == ["新任务一", "新任务二"]
    os.remove(path)


def test_reader_ttl_and_dedupe():
    fd, path = tempfile.mkstemp(suffix=".log")
    os.close(fd)
    now = [1_700_000_100.0]
    reader = HookLogReader(path, ttl=120, clock=lambda: now[0])

    with open(path, "w", encoding="utf-8") as fp:
        fp.write("M\t1700000000\ttrigger\t太旧了\n")      # 100 s 前：保留
        fp.write("M\t1699999000\ttrigger\t更旧\n")         # 1100 s 前：丢弃
        fp.write("M\t1700000099\ttrigger\t重复\n")
        fp.write("M\t1700000099\ttrigger\t重复\n")         # 2 s 内重复：丢弃

    texts = [m.text for m in reader.poll()]
    assert texts == ["太旧了", "重复"], texts
    os.remove(path)


# ---------------------------------------------------------------------------
# 运行入口
# ---------------------------------------------------------------------------

def main():
    tests = [(name, fn) for name, fn in sorted(globals().items())
             if name.startswith("test_") and callable(fn)]
    failed = 0
    for name, fn in tests:
        try:
            fn()
            print(f"  PASS  {name}")
        except AssertionError as exc:
            failed += 1
            print(f"  FAIL  {name}: {exc}")
        except Exception as exc:                       # noqa: BLE001
            failed += 1
            print(f"  ERROR {name}: {type(exc).__name__}: {exc}")
    print(f"\n{len(tests) - failed}/{len(tests)} passed")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
