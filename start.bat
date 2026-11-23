@echo off
setlocal enabledelayedexpansion
cd /d "%~dp0"
title Paper Assistant

echo ============================================
echo    Paper Assistant - One Click Start
echo ============================================
echo.

REM === 1. Clean old process ===
echo [1/3] Cleaning old processes...

if exist "server.pid" (
    set /p OLDPID=<server.pid
    if not "!OLDPID!"=="" (
        tasklist /fi "PID eq !OLDPID!" /fo table /nh 2>nul | findstr /r "[0-9]" >nul 2>&1
        if not errorlevel 1 (
            echo   Closing previous server ^(PID !OLDPID!^)...
            taskkill /f /pid !OLDPID! >nul 2>&1
        )
    )
    del /q server.pid >nul 2>&1
)

for /f "tokens=5" %%a in ('netstat -ano ^| findstr ":8000" ^| findstr "LISTENING"') do (
    echo   Closing port-8000 process ^(PID %%a^)...
    taskkill /f /pid %%a >nul 2>&1
)

echo   Done
echo.

REM === 2. Find Python (prefer project venv) ===
echo [2/3] Finding Python...
set "PYTHON="

if exist "%~dp0venv\Scripts\python.exe" set "PYTHON=%~dp0venv\Scripts\python.exe"
if exist "%~dp0python\python.exe" set "PYTHON=%~dp0python\python.exe"

if "%PYTHON%"=="" (
    for %%p in (
        "D:\python\python.exe"
        "C:\Python313\python.exe"
        "C:\Python312\python.exe"
        "C:\Python311\python.exe"
        "C:\Python310\python.exe"
    ) do (
        if exist %%p if "!PYTHON!"=="" set "PYTHON=%%~p"
    )
)

if "%PYTHON%"=="" (
    for /f "delims=" %%i in ('where python 2^>nul') do (
        if "!PYTHON!"=="" set "PYTHON=%%i"
    )
)

if "%PYTHON%"=="" (
    echo   [ERROR] Python not found!
    echo.
    pause
    exit /b 1
)

REM === Auto-create venv + install deps on first run ===
if not exist "%~dp0venv\Scripts\python.exe" (
    echo   [SETUP] Creating virtualenv ^(first run, one-time^)...
    "%PYTHON%" -m venv "%~dp0venv"
    if exist "%~dp0venv\Scripts\python.exe" (
        echo   [SETUP] Installing dependencies...
        "%~dp0venv\Scripts\python.exe" -m pip install -r "%~dp0requirements.txt" -i https://pypi.tuna.tsinghua.edu.cn/simple --disable-pip-version-check
        set "PYTHON=%~dp0venv\Scripts\python.exe"
    ) else (
        echo   [WARN] venv creation failed, fallback to system Python.
    )
)

echo   Python: %PYTHON%
echo ============================================
echo.

REM === 3. Start server in current window ===
echo [3/3] Starting server...
echo   Server will run in THIS window. Keep it open.
echo   Visit: http://127.0.0.1:8000
echo ============================================
echo.

"%PYTHON%" -u "%~dp0start.py"

echo.
echo ============================================
echo   Server stopped.
echo ============================================
pause
endlocal