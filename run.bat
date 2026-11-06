@echo off
setlocal enabledelayedexpansion
title Campus Bus Tracker

cd /d "%~dp0"

where python >nul 2>&1
if %ERRORLEVEL% equ 0 (
    set "PY_CMD=python"
) else (
    where py >nul 2>&1
    if %ERRORLEVEL% equ 0 (
        set "PY_CMD=py"
    ) else (
        echo [ERROR] Python is not installed or not added to PATH!
        pause
        exit /b 1
    )
)

%PY_CMD% server.py
if %ERRORLEVEL% neq 0 (
    echo.
    echo Server process terminated.
    pause
)
