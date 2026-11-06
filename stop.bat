@echo off
setlocal enabledelayedexpansion
title Stop Campus Bus Tracker

echo ==============================================================
echo            STOPPING CAMPUS BUS TRACKER SERVER
echo ==============================================================
echo.

set "STOPPED=0"

for %%p in (8080 8081 8082 8083) do (
    for /f "tokens=5" %%a in ('netstat -ano ^| findstr ":%%p" ^| findstr "LISTENING"') do (
        set "TARGET_PID=%%a"
        if defined TARGET_PID (
            if not "!TARGET_PID!"=="0" (
                echo [*] Terminating process on port %%p with PID !TARGET_PID!
                taskkill /F /PID !TARGET_PID! >nul 2>&1
                set "STOPPED=1"
            )
        )
    )
)

if "!STOPPED!"=="1" (
    echo.
    echo [OK] Campus Bus Tracker has been stopped.
) else (
    echo.
    echo [i] No active Campus Bus Tracker server found.
)

ping 127.0.0.1 -n 3 >nul
