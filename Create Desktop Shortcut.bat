@echo off
setlocal enabledelayedexpansion
title Create Desktop Shortcut - Campus Bus Tracker

cd /d "%~dp0"

where python >nul 2>&1
if %ERRORLEVEL% equ 0 (
    set "PY_CMD=python"
) else (
    where py >nul 2>&1
    if %ERRORLEVEL% equ 0 (
        set "PY_CMD=py"
    ) else (
        echo [ERROR] Python is not installed or not in PATH.
        pause
        exit /b 1
    )
)

%PY_CMD% create_shortcut.py
echo.
pause
