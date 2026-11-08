-- ============================================================================
-- awacs_hook.lua — DCS 用户钩子：把游戏内文字通报原样落盘
--
-- 安装
--   复制到 <Saved Games>\<DCS 变体>\Scripts\Hooks\awacs_hook.lua
--   （与 TacviewGameGUI.lua / DCS-SRS-hook.lua 同目录；DCS 启动时按文件名排序加载，
--     运行中新增或修改不生效，必须重启游戏）
--
-- 输出
--   %LOCALAPPDATA%\AWACSMARK\messages.log
--   与 Saved Games 的位置无关 —— 用户把存档目录搬到哪个盘都不影响读取。
--
-- 格式（TAB 分隔，一行一条）
--   M <epoch> <trigger|radio|chat> <转义后的文本>
--   H <epoch> <modelTime>          心跳，每 5 s 一行
--   R                              日志因超限被截断
--
-- 体积控制（不会无限增长）
--   * 每次任务开始 onSimulationStart 时截断重写；
--   * 累计写入超过 1 MB 时截断并写一行 R；
--   * 心跳每 5 s 一行（约 10 字节）。
--
-- 依据：API\Sim_ControlAPI.md —— 用户钩子加载进 GUI Lua 状态，
--       回调通过 Sim.setUserCallbacks / DCS.setUserCallbacks 注册。
-- ============================================================================

local lfs = lfs or require('lfs')
local API = Sim or DCS

-- ---- 路径 ------------------------------------------------------------------

local baseDir = os.getenv('LOCALAPPDATA')
if not baseDir or baseDir == '' then
    baseDir = lfs.writedir()          -- 兜底：极少见，LOCALAPPDATA 一定存在
end
local OUT_DIR = baseDir .. '\\AWACSMARK'
local OUT_PATH = OUT_DIR .. '\\messages.log'

pcall(lfs.mkdir, OUT_DIR)             -- 已存在会返回 nil, "File exists"，忽略

-- ---- 文件与计数 ------------------------------------------------------------

local file = nil
local bytesWritten = 0
local MAX_BYTES = 1024 * 1024         -- 1 MB
local lastBeat = 0
local BEAT_INTERVAL = 5               -- 秒

local function closeFile()
    if file then
        pcall(function() file:close() end)
        file = nil
    end
end

local function openFile(mode)
    closeFile()
    bytesWritten = 0
    local ok, f = pcall(io.open, OUT_PATH, mode or 'w')
    if ok and f then
        file = f
        if mode == 'a' then
            -- 追加模式下先量一下已有体积，保证 1 MB 上限仍然有效
            local pos = file:seek('end')
            bytesWritten = pos or 0
        end
    else
        file = nil
    end
end

local function ensureFile()
    if not file then
        openFile('a')
    end
    return file ~= nil
end

-- ---- 写入 ------------------------------------------------------------------

local function escape(text)
    local s = tostring(text)
    s = s:gsub('\\', '\\\\')
    s = s:gsub('\n', '\\n')
    s = s:gsub('\t', '\\t')
    return s
end

local function writeLine(line)
    if not ensureFile() then
        return
    end

    if bytesWritten > MAX_BYTES then
        openFile('w')
        if file then
            file:write('R\n')
            file:flush()
        end
        bytesWritten = 2
    end

    if file then
        local ok = pcall(function()
            file:write(line, '\n')
            file:flush()              -- 立即落盘，Python 侧才能低延迟读到
        end)
        if not ok then
            closeFile()
        else
            bytesWritten = bytesWritten + #line + 1
        end
    end
end

local function push(kind, text)
    if text == nil or text == '' then
        return
    end
    writeLine(string.format('M\t%d\t%s\t%s', os.time(), kind, escape(text)))
end

local function beat()
    local now = os.time()
    if now - lastBeat < BEAT_INTERVAL then
        return
    end
    lastBeat = now
    local modelTime = 0
    if API and API.getModelTime then
        modelTime = API.getModelTime() or 0
    end
    writeLine(string.format('H\t%d\t%.1f', now, modelTime))
end

-- ---- 回调 ------------------------------------------------------------------

local cb = {}

function cb.onSimulationStart()
    openFile('w')                     -- 每局一个全新的日志
    lastBeat = 0
    beat()
end

function cb.onSimulationStop()
    closeFile()
end

function cb.onTriggerMessage(message)
    push('trigger', message)
end

function cb.onRadioMessage(message)
    push('radio', message)
end

function cb.onChatMessage(message, from)
    push('chat', tostring(from) .. ':' .. tostring(message))
end

-- onShowMessage 与 onTriggerMessage 可能对同一条文本各触发一次；
-- Python 侧有 2 s 去重窗口，这里照收不误即可保证不漏。
function cb.onShowMessage(text)
    push('trigger', text)
end

function cb.onSimulationFrame()
    beat()
end

if API and API.setUserCallbacks then
    API.setUserCallbacks(cb)
else
    print('[AWACSMARK] 钩子注册失败：Sim/DCS.setUserCallbacks 不可用')
end
