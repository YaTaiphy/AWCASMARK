-- ============================================================================
-- AWCSMARK.lua — DCS World 飞行数据 UDP 导出（17 字段 CSV）
--
-- 变更（2026-11）
--   * 发送频率 30 Hz → 10 Hz：界面约 60 fps 重绘，10 Hz 数据已足够，
--     同时把 Python 侧的解包与信号派发量降到 1/3。
--   * socket 异常自愈：目标端口没监听时（游戏开着、工具没开），Windows 可能
--     回 ICMP port unreachable，使下一次 send 失败；此时关闭并重建 socket，
--     避免"数据突然没了，必须重开任务才恢复"。
--   * 任务开始前先关闭旧句柄，避免反复重开任务时泄漏 socket。
--
-- 安装
--   保存到 <Saved Games>\<DCS 变体>\Scripts\AWCSMARK.lua，并在同目录 Export.lua 中：
--     local lfs = require('lfs')
--     dofile(lfs.writedir() .. 'Scripts/AWCSMARK.lua')
--
-- 数据格式（17 字段，逗号分隔，单位：米 / 度 / 米每秒）
--   1  TIME                 游戏模型时间 (s)
--   2  PosX                 北向坐标 (m)
--   3  PosY                 高度 (m)
--   4  PosZ                 东向坐标 (m)
--   5  Heading              航向 (°)
--   6  Pitch                俯仰 (°)
--   7  Bank                 横滚 (°)
--   8  Lat                  纬度 (°)
--   9  Long                 经度 (°)
--  10  Height               海拔 (m，LatLongAlt.Alt)
--  11  AltBar               气压高度 (m)
--  12  AltRad               雷达高度 (m)
--  13  TrueAirSpeed         真空速 (m/s)
--  14  IndicatedAirSpeed    指示空速 (m/s)
--  15  VelX                 速度矢量 X (m/s)
--  16  VelY                 速度矢量 Y (m/s)
--  17  VelZ                 速度矢量 Z (m/s)
-- ============================================================================

local socket = require("socket")

local HOST = "127.0.0.1"
local PORT = 12345
local SEND_INTERVAL = 1 / 10 -- 10 Hz（原 30 Hz）
local SEND_FORMAT = "%.3f,%.2f,%.2f,%.2f,%.4f,%.4f,%.4f,%.4f,%.4f,%.4f,%.2f,%.2f,%.2f,%.2f,%.4f,%.4f,%.4f"

local udp = nil
local lastSendWallTime = 0

-- 串联其它导出脚本（Tacview / SRS / MOZA 等），保持原有调用链
local prevLuaExportStart = LuaExportStart
local prevLuaExportAfterNextFrame = LuaExportAfterNextFrame
local prevLuaExportStop = LuaExportStop

-- ---------------------------------------------------------------------------
-- socket 管理
-- ---------------------------------------------------------------------------

local function closeSocket()
    if udp then
        pcall(udp.close, udp)
        udp = nil
    end
end

local function openSocket()
    closeSocket()
    local ok = pcall(function()
        udp = socket.udp()
        udp:setpeername(HOST, PORT)
        udp:settimeout(0) -- 非阻塞，绝不拖慢游戏帧
    end)
    if not ok then
        udp = nil
        return false
    end
    return true
end

-- ---------------------------------------------------------------------------
-- 导出回调
-- ---------------------------------------------------------------------------

function LuaExportStart()
    openSocket()
    lastSendWallTime = 0

    if prevLuaExportStart then
        pcall(prevLuaExportStart)
    end
end

function LuaExportAfterNextFrame()
    -- 用墙上时钟做帧率控制：模型时间在暂停时会冻结，会导致数据断流
    local now = socket.gettime()

    if now - lastSendWallTime >= SEND_INTERVAL then
        lastSendWallTime = now

        if not udp then
            openSocket()
        end

        if udp then
            -- pcall 包住全部逻辑：任何 Lua 错误都不能中断导出链
            local ok = pcall(function()
                local selfData = LoGetSelfData()
                if selfData == nil then
                    return
                end

                local pos = selfData.Position
                local radToDeg = 180 / math.pi
                local vel = selfData.Velocity or { x = 0, y = 0, z = 0 }

                local sendStr = string.format(
                    SEND_FORMAT,
                    LoGetModelTime(),
                    pos.x, pos.y, pos.z,
                    selfData.Heading * radToDeg,
                    selfData.Pitch * radToDeg,
                    selfData.Bank * radToDeg,
                    selfData.LatLongAlt.Lat,
                    selfData.LatLongAlt.Long,
                    selfData.LatLongAlt.Alt,
                    LoGetAltitudeAboveSeaLevel() or 0,
                    LoGetAltitudeAboveGroundLevel() or 0,
                    LoGetTrueAirSpeed() or 0,
                    LoGetIndicatedAirSpeed() or 0,
                    vel.x, vel.y, vel.z
                )

                -- send 失败返回 nil（不抛错），转成异常以便统一走重建分支
                local sent = udp:send(sendStr)
                if not sent then
                    error("udp send failed")
                end
            end)

            if not ok then
                -- 端口未监听/ICMP 导致的 socket 错误：重建，下一帧继续
                closeSocket()
            end
        end
    end

    if prevLuaExportAfterNextFrame then
        pcall(prevLuaExportAfterNextFrame)
    end
end

function LuaExportStop()
    closeSocket()

    if prevLuaExportStop then
        pcall(prevLuaExportStop)
    end
end
