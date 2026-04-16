@echo off
title JARVIS — Desktop AI Assistant
cd /d "%~dp0"
echo.
echo  ######################################
echo  #     JARVIS — Desktop AI Assistant  #
echo  ######################################
echo.

:: Check for Python
python --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python not found. Download from python.org and add to PATH.
    pause
    exit /b 1
)

:: Install dependencies
echo [1/3] Installing dependencies...
pip install -r requirements.txt --quiet

echo [2/3] System snapshot will load on first run (takes ~10 seconds).
echo [3/3] Launching JARVIS...
echo.

python main.py
pause
