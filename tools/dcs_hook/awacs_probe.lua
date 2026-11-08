-- ============================================================================
-- awacs_probe.lua — DCS 用户钩子「探针」
--
-- 用途：把游戏内所有“文字类”GUI 回调原样落盘，用来确认预警机通报到底走
--       哪个回调（onShowMessage / onTriggerMessage / onRadioMessage / chat）。
--       确认之后，再决定把 AWACSMARK 的截图 OCR 换成哪个来源。
--
-- 安装：复制到
--       <Saved Games>\<DCS 变体>\Scripts\Hooks\awacs_probe.lua
--       本机实测写目录为 C:\Users\adminstor\Saved Games\DCS F-100D
--       （没有 Scripts 目录就自己建：Scripts\Hooks\）
--       DCS 启动时按文件名排序加载该目录，运行中新增/修改不会生效，需重启游戏。
--
-- 输出：<Saved Games>\<DCS 变体>\Logs\awacs_probe.log
--
-- 依据：API\Sim_ControlAPI.md（官方《Simulation Control User Scripts》）
--       - 用户钩子加载进 GUI Lua 状态，每个脚本独立环境（isolated environment）
--       - 回调通过 Sim.setUserCallbacks(cb_table) 注册
--       - GUI 回调列表含 onShowMessage / onTriggerMessage / onRadioMessage /
--         onRadioCommand / onChatMessage
-- ============================================================================

local lfs = lfs or require('lfs')
local API = Sim or DCS          -- 新文档用 Sim.*，旧代码/系统钩子里是 DCS.*

local LOG = lfs.writedir() .. 'Logs\\awacs_probe.log'
local file = io and io.open(LOG, 'a')

local function stamp()
    return os.date('%H:%M:%S')
end

local function log(tag, ...)
    local n = select('#', ...)
    local parts = {}
    for i = 1, n do
        parts[i] = tostring((select(i, ...)))
    end
    local line = string.format('[%s] %-16s %s', stamp(), tag, table.concat(parts, '  |  '))
    if file then
        file:write(line, '\n')
        file:flush()            -- 立即落盘，Python 侧可以 tail -f
    end
    print(line)                 -- 同时进 dcs.log，双保险
end

log('PROBE', 'loaded; writedir=' .. lfs.writedir())

local cb = {}

-- ---- 仿真/任务生命周期 -----------------------------------------------------
function cb.onSimulationStart()
    local name = '?'
    if API.getMissionName then name = tostring(API.getMissionName()) end
    log('SIM_START', 'mission=' .. name)
end

-- ---- 文字消息：四个候选入口，全挂上，看哪个真的被调用 ---------------------
-- 任务脚本 trigger.action.outText / outTextForCoalition 一般走这两个
function cb.onShowMessage(text, duration)
    log('onShowMessage', text, duration)
end

function cb.onTriggerMessage(message, duration, clearView)
    log('onTriggerMessage', message, duration, clearView)
end

-- 无线电呼叫字幕（预警机语音播报的文字版）
function cb.onRadioMessage(message, duration, subtitles, subtitlesDuration)
    log('onRadioMessage', message, duration, subtitles, subtitlesDuration)
end

-- 无线电菜单当前项（会非常频繁，仅用于观察，正式版可以删掉）
function cb.onRadioCommand(commandMessage)
    if commandMessage and commandMessage ~= '' then
        log('onRadioCommand', commandMessage)
    end
end

-- 多人聊天（真人 GCI 用聊天发通报时走这里）
function cb.onChatMessage(message, from)
    log('onChatMessage', message, from)
end

-- ---- 多人聊天补漏：轮询聊天历史（防止 onChatMessage 漏掉） ----------------
-- 每 3 秒拉一次增量；不需要可以整段删除。
local lastChatIndex = 0
local lastPoll = 0
function cb.onSimulationFrame()
    if not (API.getRealTime and net and net.get_chat_history) then return end
    local now = os.time()
    if now - lastPoll < 3 then return end
    lastPoll = now
    local ok, history, idx = pcall(net.get_chat_history, lastChatIndex)
    if not ok or type(history) ~= 'table' or #history == 0 then return end
    for _, item in ipairs(history) do
        -- item = {abstime, side, playerName, message}；兼容具名字段
        local who = item.playerName or item[3]
        local msg = item.message or item[4]
        log('chat_hist', tostring(who), tostring(msg))
    end
    lastChatIndex = idx or (lastChatIndex + #history)
end

API.setUserCallbacks(cb)
