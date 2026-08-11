# AWACSMARK — DCS World 预警机标记辅助工具

## 项目简介

AWACSMARK 是一款面向 **DCS World** 飞行模拟游戏的辅助工具。它通过 OCR 识别游戏中预警机（AWACS）的语音/文字通报信息，将敌机位置、高度、航向等数据实时绘制在雷达覆盖窗上，帮助玩家快速掌握战场态势。

支持中英文两种预警机通报格式、队友位置共享，以及多种雷达显示模式。

## 核心功能

| 功能 | 说明 |
|------|------|
| **敌机标记** | 截图 → OCR 识别 → 解析 BRA/牛眼通报 → 在圆形雷达图上标绘敌机位置、高度、航向箭头 |
| **接敌状态** | 自动识别 HOT（迎头）/ COLD（追击）/ FLANK（侧对），箭杆方向跟随敌机航向 |
| **时间衰减** | 标记颜色随残留时间逐步淡出，避免新旧 contact 重叠混淆 |
| **友机显示** | 通过远程服务器共享队友位置，以蓝色标记显示于雷达图上 |
| **三种显示模式** | 中心绝对方位（NGAS）、底部中心-机头向上（SA）、中心-机头向上 |
| **简要模式** | 一键切换无边框全屏雷达（可拖动 + 可调尺寸），适合叠加在游戏画面上 |
| **多比例尺** | 支持 50/100/200 km 或 25/50/100 nm 比例尺切换 |
| **多服务器模式** | 中文预警机、英文预警机、SPS 服务器、BSC 服务器 |
| **窗口置顶 & 透明度** | 支持窗口置顶和透明度滑块调节（20%–100%） |
| **本地 UDP 数据** | 监听 `127.0.0.1:12345` 获取 DCS 导出的本机坐标与航向 |

## 系统架构

```
main.py (入口 ~30 行)
  └─ QApplication → MainWindow
                      │
       ┌──────────────┼──────────────┐
       ▼              ▼              ▼
  ui/            radar/          worker/
  main_window   renderer        ocr_worker
  settings_dlg  grid            team_worker
  radar_widget  aircraft
  area_selector      │
       │              ▼
       ▼           utils.py
  network/         (数学函数)
  udp_listener
  http_client
       │
       ▼
  ocr/
  client     (流程编排: 上传→解析→去重→过期)
  parser     (文本解析: BRA/牛眼/SPS/BSC)
  screenshot (mss 截图)
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
| **网络** | [network/udp_listener.py](network/udp_listener.py) | UDP Socket 监听 DCS 飞行数据 |
| | [network/http_client.py](network/http_client.py) | HTTP 通信：OCR 图片上传、队友同步、TCP 预检 |
| **OCR** | [ocr/parser.py](ocr/parser.py) | 通报文本解析：中文/英文 BRA、牛眼、SPS、BSC |
| | [ocr/screenshot.py](ocr/screenshot.py) | mss 屏幕截图 |
| | [ocr/client.py](ocr/client.py) | OCR 客户端：发送→解析→去重→过期清理 |
| **雷达** | [radar/grid.py](radar/grid.py) | 雷达网格绘制（同心圆、径向线、方向标识） |
| | [radar/aircraft.py](radar/aircraft.py) | 飞机标记绘制（敌机/友机 × 绝对/相对方位） |
| | [radar/renderer.py](radar/renderer.py) | 渲染编排：统一的 paint 入口 |
| **Worker** | [worker/ocr_worker.py](worker/ocr_worker.py) | 持久化 OCR 工作线程（`@Slot` + `QueuedConnection`） |
| | [worker/team_worker.py](worker/team_worker.py) | 持久化队友同步线程（含指数退避） |
| **UI** | [ui/main_window.py](ui/main_window.py) | 主窗口：控件初始化、定时器、信号/槽、工作线程管理 |
| | [ui/settings_dialog.py](ui/settings_dialog.py) | 参数配置对话框 |
| | [ui/radar_widget.py](ui/radar_widget.py) | 独立雷达绘制控件（QWidget paintEvent） |
| | [ui/area_selector.py](ui/area_selector.py) | 全屏截图 + 鼠标拖拽框选截取区域 |
| **工具** | [utils.py](utils.py) | 数学函数：方位/距离计算、坐标偏移 |
| **遗留** | [window.py](window.py) | Qt Designer 自动生成（Ui_MA） |
| | [arsInputDialog.py](arsInputDialog.py) | Qt Designer 自动生成（Ui_argsDialog） |

## 技术栈

| 层级 | 技术 |
|------|------|
| **GUI 框架** | PySide6 (Qt for Python 6) |
| **UI 设计** | Qt Designer (`.ui` → `.py` via `pyside6-uic`) |
| **OCR 引擎** | 远程 Flask 服务器（HTTP POST /upload，支持中英文） |
| **屏幕截图** | `mss` 库 |
| **图像处理** | Pillow (PIL) |
| **网络通信** | UDP Socket（本机数据流）、HTTP/JSON（远程 OCR & 队友同步） |
| **打包工具** | Nuitka (`--onefile --windows-disable-console --enable-plugin=pyside6`) |
| **语言** | Python 3.13+ |

## 运行环境

- **操作系统**: Windows 10/11
- **Python**: 3.13+
- **依赖库**: `PySide6`, `mss`, `Pillow`, `numpy`

## 使用方法

### 1. 启动前准备

1. 在 DCS World 中配置 Lua 脚本，向 `127.0.0.1:12345` 发送本机飞行数据（UDP 格式: `timestamp,x,y,z,heading,pitch,bank,lat,long,height`）
2. 确保远程 OCR/队友同步服务器已启动（默认 `121.41.75.139:10386`）

### 2. 启动程序

```bash
python main.py
```

### 3. 配置参数

点击工具栏 **信息查看** 按钮，在设置对话框中填写：

| 参数 | 说明 |
|------|------|
| **代号 (Callsign)** | 预警机对你的呼号（如 `Dodge 1-1`） |
| **靶眼坐标** | 任务编辑器中 Bullseye 的 X/Z 坐标 |
| **截图区域** | 预警机通报文字在屏幕上的区域（可拖拽选取） |
| **预警机单位** | 预警机通报使用的计量单位（km 或 nm） |
| **服务器模式** | 0=中文预警机, 1=英文预警机, 2=SPS, 3=BSC |
| **小队代码** | 用于队友位置同步的队伍标识 |
| **敌机残留时间** | 标记在屏幕上保留的秒数（默认 90 秒） |
| **功能开关** | 敌机显示 / 队友显示 / 使用默认服务器 |

### 4. 开始任务

点击 **开始** 按钮启动：
- UDP 数据监听 → 获取本机位置和航向
- 定时截图 → OCR 识别 → 雷达图实时更新
- 队友位置轮询

### 5. 运行中调整

| 操作 | 方式 |
|------|------|
| **显示模式** | 工具栏下拉框：中心 / 直对 / 中心直对 |
| **比例尺** | 右侧垂直滑块：50km / 100km / 200km |
| **单位制** | 工具栏下拉框：km / nm |
| **窗口置顶** | 雷达左上角「置顶」复选框 |
| **透明度** | 左侧垂直滑块：20%–100% |
| **简要模式** | 工具栏「简要」按钮，无边框全屏雷达 |

## 显示模式详解

### 中心模式（NGAS / 绝对方位）
- 本机始终位于窗口**中心**，正上 = 北，正右 = 东
- 视图**不随航向旋转**
- 类似传统北向上雷达

### 直对模式（SA / 机头向上）
- 本机位于窗口**底部中央**
- 视图**随本机航向旋转**，正上 = 机头方向
- 类似战斗机 HSD 的 SA 模式

### 中心直对模式
- 本机位于窗口**中心**
- 视图**随本机航向旋转**

## 数据流

```
DCS World (Lua Export)
    │  UDP :12345
    ▼
[network/udp_listener.py] SocketWorker (专用线程)
    │  signal: data_received
    ▼
[ui/main_window.py] _on_udp_data() → 更新 plane_data
    │
    ├─── QTimer (400ms) ─── [ocr/screenshot.py] mss 截图 → screen_shot_list
    │
    └─── QTimer (1000ms) ── _tick_ocr()
                                │
                    configure() + QMetaObject.invokeMethod → OCRWorker (专用线程)
                                │
                                ▼
                    [ocr/client.py] process_screenshots()
                                │  HTTP POST /upload (JSON + base64 PNG)
                                ▼
                    远程 OCR Flask 服务器
                                │
                                ▼ JSON 识别文本
                    [ocr/parser.py] 解析 BRA/牛眼 → 坐标、航向、高度
                                │
                                ▼ signal: data_received
                    [ui/main_window.py] _on_ocr_result() → 更新 message_dic
                                │
                                ▼
                    [ui/radar_widget.py] paintEvent → [radar/renderer.py] render()
```

## 英文预警机模式

支持 DCS 英文 AWACS 通报格式（server_mode=1）：

```
Overlord1-1: Dodge 4, Overlord1-1, pop-up group, 314 for 110, at altitude 3500, hot
```

- **BRA 格式**: `bearing for range`（如 `314 for 110` = 方位 314°，距离 110）
- **接敌状态**: `hot` → 机头朝向本机, `cold` → 背离, `flanking` → 侧对
- **高度**: `at altitude N`（千英尺）

## 配置持久化

所有配置保存在 `%LOCALAPPDATA%\AWACASConfig.json`（JSON 格式）。启动时自动加载，确认设置后自动保存。

## 日志

- **控制台**: INFO 级别，仅显示重要事件（OCR 结果、用户操作、网络错误等）
- **文件**: `logs/app.log` — DEBUG 级别完整记录，自动轮转（1MB × 3 备份）
- 排查问题时查看日志文件可获得完整的事件序列和调试信息

## 打包构建

```bash
python -m nuitka --onefile --windows-disable-console --enable-plugin=pyside6 --follow-import-to=need --output-dir=output main.py
```

## 开发说明

### UI 修改流程
1. 使用 Qt Designer 编辑 `.ui` 文件
2. `pyside6-uic untitled.ui -o window.py` 重新生成 UI 代码
3. `pyside6-uic dialog.ui -o arsInputDialog.py` 重新生成对话框代码

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
  network/             HTTP/UDP 通信
  ocr/                 OCR 识别与解析
  radar/               雷达绘制
  ui/                  GUI 组件
  worker/              工作线程
```

## License

内部项目，仅供 DCS World 模拟飞行使用。
