# AWACSMARK — DCS World 预警机标记辅助工具

## 项目简介

AWACSMARK 是一款面向 **DCS World** 飞行模拟游戏的辅助工具。它通过 **DCS 用户钩子（GUI Lua 回调）**
直接读取游戏内预警机的文字通报，把敌机方位、距离、高度、航向实时绘制在雷达覆盖窗上，
帮助玩家快速掌握战场态势。

> **重要变更（2026-11）**：消息来源已从「截图 + OCR」改为「DCS 用户钩子」。
> 不再需要截屏、不再上传图片、不再依赖远程 OCR 服务，识别结果为原始文本、零误识、毫秒级延迟。
> 旧的 OCR 链路与截图设置页已移除。

支持中英文两种预警机通报格式、SPS/BSC 面板格式、队友位置共享，以及多种雷达显示模式。

## 核心功能

| 功能 | 说明 |
|------|------|
| **敌机标记** | 游戏内文字回调 → 文本解析 → 在圆形雷达图上标绘敌机位置、高度、航向箭头 |
| **通道路由** | 按文本特征自动区分 SPS 面板 / 传统 BRA / 牛眼 / 英文格式，无需手选服务器类型 |
| **接敌状态** | 自动识别 HOT（迎头）/ COLD（追击）/ FLANK（侧对），箭杆方向跟随敌机航向 |
| **时间衰减** | 标记颜色随残留时间逐步淡出；同一目标被再次播报时自动续命 |
| **友机显示** | 通过远程服务器共享队友位置，以蓝色标记显示于雷达图上 |
| **三种显示模式** | 中心绝对方位（NGAS）、底部中心-机头向上（SA）、中心-机头向上 |
| **简要模式** | 一键切换无边框全屏雷达（可拖动 + 可调尺寸），适合叠加在游戏画面上 |
| **多比例尺** | 支持 50/100/200 km 或 25/50/100 nm 比例尺切换 |
| **多服务器模式** | 中文预警机、英文预警机、SPS 服务器、BSC 服务器（自动识别） |
| **窗口置顶 & 透明度** | 支持窗口置顶和透明度滑块调节（20%–100%） |
| **本地 UDP 数据** | 监听 `127.0.0.1:12345` 获取 DCS 导出的本机坐标与航向 |

## 系统架构

```
main.py (入口 ~20 行)
  └─ QApplication → MainWindow
                      │
       ┌──────────────┼───────────────┐
       ▼              ▼               ▼
   ui/            radar/          dcs/
   main_window   renderer        hook_source  (增量读日志)
   settings_dlg  grid            protocol     (行协议)
   radar_widget  aircraft        router       (特征分流)
                                 pipeline     (写入敌情)
                                 parser       (文本解析)
       │              │               │
       ▼              ▼               ▼
   network/        utils.py        worker/
   udp_listener    (数学函数)      team_worker
   http_client
       │
       ▼
   config.py  ←→  constants.py
   (JSON 持久化)   (枚举 & 魔法值)
```

### 模块职责

| 层 | 文件 | 职责 |
|----|------|------|
| **入口** | [main.py](main.py) | 仅创建 QApplication + 实例化 MainWindow |
| **配置** | [config.py](config.py) | 单例 `AppConfig` 类，JSON 持久化 |
| **常量** | [constants.py](constants.py) | 所有魔法数字、枚举值、定时器间隔、颜色定义 |
| **日志** | [log.py](log.py) | 统一日志模块：控制台 INFO + 文件 DEBUG + 自动轮转 |
| **消息源** | [dcs/hook_source.py](dcs/hook_source.py) | 增量读取钩子日志（只读新字节、截断自愈、心跳判活） |
| | [dcs/protocol.py](dcs/protocol.py) | 日志行协议：`M` 消息 / `H` 心跳 / `R` 截断标记 |
| | [dcs/router.py](dcs/router.py) | 按文本特征分流到 SPS / 传统 BRA / 牛眼 / 英文 |
| | [dcs/pipeline.py](dcs/pipeline.py) | 写入 `message_dic`：续命、重算坐标、记录单位与来源 |
| | [dcs/parser.py](dcs/parser.py) | 通报文本解析：中文/英文 BRA、牛眼、SPS/BSC 面板 |
| **网络** | [network/udp_listener.py](network/udp_listener.py) | UDP Socket 监听 DCS 飞行数据（本机位置/航向/高度） |
| | [network/http_client.py](network/http_client.py) | 队友位置同步、服务器可达性检查 |
| **雷达** | [radar/grid.py](radar/grid.py) | 雷达网格绘制（同心圆、径向线、方向标识） |
| | [radar/aircraft.py](radar/aircraft.py) | 飞机标记绘制（敌机/友机 × 绝对/相对方位） |
| | [radar/renderer.py](radar/renderer.py) | 渲染编排：统一的 paint 入口 + 飞行数据面板 |
| **Worker** | [worker/team_worker.py](worker/team_worker.py) | 持久化队友同步线程（含指数退避） |
| **UI** | [ui/main_window.py](ui/main_window.py) | 主窗口：控件、定时器、信号/槽、工作线程管理 |
| | [ui/settings_dialog.py](ui/settings_dialog.py) | 参数配置对话框 |
| | [ui/radar_widget.py](ui/radar_widget.py) | 独立雷达绘制控件（QWidget paintEvent） |
| **工具** | [utils.py](utils.py) | 数学函数：方位/距离计算、坐标偏移 |
| **遗留** | [window.py](window.py) | Qt Designer 自动生成（Ui_MA） |
| | [arsInputDialog.py](arsInputDialog.py) | Qt Designer 自动生成（Ui_argsDialog） |

## 技术栈

| 层级 | 技术 |
|------|------|
| **GUI 框架** | PySide6 (Qt for Python 6) |
| **UI 设计** | Qt Designer (`.ui` → `.py` via `pyside6-uic`) |
| **消息来源** | DCS 用户钩子（GUI Lua 状态，`Scripts/Hooks/*.lua`） |
| **本机数据** | UDP Socket（DCS Lua Export，10 Hz） |
| **网络通信** | HTTP/JSON（队友同步） |
| **打包工具** | Nuitka (`--onefile --windows-disable-console --enable-plugin=pyside6`) |
| **语言** | Python 3.13+ |

## 运行环境

- **操作系统**: Windows 10/11
- **Python**: 3.13+
- **依赖库**: `PySide6`（消息解析与显示不再需要 mss / Pillow / 远程 OCR 服务）

## 安装与使用

> 完整图文说明（安装、脚本位置、原理、FAQ）见 [操作说明-v4.0.html](操作说明-v4.0.html)。

### 1. 安装消息钩子（必需）

把 [tools/dcs_hook/awacs_hook.lua](tools/dcs_hook/awacs_hook.lua) 复制到：

```
<Saved Games>\<DCS 变体>\Scripts\Hooks\awacs_hook.lua
```

没有 `Hooks` 目录就自己建。**钩子只在 DCS 启动时加载，装完必须重启游戏。**

### 2. 安装飞行数据导出（必需）

`<Saved Games>\<DCS 变体>\Scripts\` 下放 [版本号/AWCSMARK.lua](版本号/AWCSMARK.lua)，
并在同目录 `Export.lua` 末尾加一行：

```lua
local lfs = require('lfs')
dofile(lfs.writedir() .. 'Scripts/AWCSMARK.lua')
```

它每 100 ms 通过 UDP 向 `127.0.0.1:12345` 发送本机坐标/航向/高度/速度（17 字段 CSV）。

### 3. 启动程序

```bash
python main.py
```

### 4. 配置参数

点击工具栏 **信息查看** 按钮：

| 参数 | 说明 |
|------|------|
| **代号 (Callsign)** | 预警机对你的呼号数字（如 SPS/传统服里的 `128`）；**只填数字** |
| **靶眼坐标** | 任务编辑器中 Bullseye 的 X/Z 坐标（牛眼通报必需） |
| **预警机单位** | `auto` / `KM` / `NM`。SPS/BSC 面板自带单位会自动识别；传统预警机没有单位，必须手选 |
| **消息格式** | `auto` 按文本自动识别（推荐）；也可强制指定 SPS 面板 / 传统(中文) / 传统(英文) / BSC 面板。SPS、BSC 只是通报的**排版格式**，与服务器类型无关 |
| **敌机残留时间** | 标记在屏幕上保留的秒数（默认 90） |
| **消息保留窗口** | 只读取最近 N 秒的通报（默认 120，应 ≥ 残留时间） |
| **小队代码** | 用于队友位置同步的队伍标识 |
| **功能开关** | 敌机显示 / 队友显示 / 使用默认服务器 |

### 5. 开始任务

点击 **开始** 按钮启动：
- UDP 数据监听 → 获取本机位置和航向
- 钩子日志监听 → 读取预警机通报 → 实时更新雷达图
- 队友位置轮询

## 显示模式详解

### 中心模式（NGAS / 绝对方位）
- 本机始终位于窗口**中心**，正上 = 北，正右 = 东，视图不随航向旋转

### 直对模式（SA / 机头向上）
- 本机位于窗口**底部中央**，视图随本机航向旋转，正上 = 机头方向

### 中心直对模式
- 本机位于窗口**中心**，视图随本机航向旋转

## 数据流

```
DCS World (任务脚本触发文字通报)
    │  GUI Lua 回调: onTriggerMessage / onRadioMessage
    ▼
[Scripts/Hooks/awacs_hook.lua]
    │  追加写: %LOCALAPPDATA%\AWACSMARK\messages.log
    ▼
[dcs/hook_source.py] 每 200 ms 只读新增字节 + 心跳判活
    │  DcsMessage(kind, text)
    ▼
[dcs/router.py] 特征分流
    │  ├─ 面板（TYPE/BRG 表头） → dcs/parser.parse_sps_panel
    │  └─ 无线电（方位/距离）   → parse_awacs_bra + parse_bullseye
    ▼
[dcs/pipeline.py] 写入 message_dic / bullseye_dic（续命 + 重算坐标）
    │
    ▼
[ui/radar_widget.py] paintEvent → [radar/renderer.py] render()

并行：
DCS World (Lua Export)
    │  UDP :12345（10 Hz，17 字段）
    ▼
[network/udp_listener.py] → [ui/main_window.py] plane_data
```

## 钩子日志格式

```
M<TAB><epoch><TAB><trigger|radio|chat><TAB><转义后的文本>
H<TAB><epoch><TAB><model_time>          # 心跳，每 5 s
R                                        # 日志被截断
```

体积控制：每局开始截断、累计 1 MB 截断、Python 侧只读最近 `message_ttl` 秒。**不会无限增长。**

## 配置持久化

所有配置保存在 `%LOCALAPPDATA%\AWACASConfig.json`，启动时自动加载，确认设置后自动保存。

## 日志

- **控制台**: INFO 级别
- **文件**: `logs/app.log` — DEBUG 级别完整记录，自动轮转（1 MB × 3 备份）
- 排查钩子问题：先看 `%LOCALAPPDATA%\AWACSMARK\messages.log` 是否有内容

## 常见问题

| 现象 | 排查 |
|---|---|
| 雷达没有任何敌机 | 钩子日志是否存在？DCS 装完钩子后是否重启？日志里是否有 `H` 心跳 |
| 所有敌机挤在中心 | UDP 飞行数据没收到：检查 `Export.lua` 是否加载了 `AWCSMARK.lua` |
| 传统预警机距离明显不对 | 设置里单位选了 `auto` 但传统通报无单位，需手选 KM 或 NM |
| 牛眼标记整体偏移 | 靶眼坐标填错，或与任务设置不一致 |

## 打包构建

```bash
python -m nuitka --onefile --windows-disable-console --enable-plugin=pyside6 \
  --follow-import-to=need --output-dir=output main.py
```

## 开发说明

### UI 修改流程
1. 使用 Qt Designer 编辑 `.ui` 文件
2. `pyside6-uic untitled.ui -o window.py` 重新生成 UI 代码
3. `pyside6-uic dialog.ui -o arsInputDialog.py` 重新生成对话框代码

### 测试

```bash
python tests/test_dcs_pipeline.py     # 解析/路由/增量读取，12 项
```

### 项目结构
```
AWCSMARK/
  main.py              入口
  config.py            配置单例
  constants.py         常量/枚举
  log.py               日志模块
  utils.py             数学工具
  window.py            UI 自动生成
  arsInputDialog.py    对话框自动生成
  dcs/                 钩子消息源（协议/读取/路由/解析/写入）
  network/             UDP / HTTP
  radar/               雷达绘制
  ui/                  GUI 组件
  worker/              队友同步线程
  tools/dcs_hook/      DCS 侧 Lua（探针 + 正式钩子）
  tests/               单元测试
```

## License

内部项目，仅供 DCS World 模拟飞行使用。
