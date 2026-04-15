@echo off
title JARVIS Setup
color 0B
echo.
echo  ===================================
echo   JARVIS - Desktop AI Assistant
echo   Setup ^& Launch
echo  ===================================
echo.

:: Check Python
python --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python not found. Please install Python 3.10+ from python.org
    pause
    exit /b 1
)

echo [*] Checking dependencies...
pip install anthropic --quiet

echo [*] Checking for pyautogui (optional, for screenshots)...
pip install pyautogui --quiet 2>nul

:: Check for API key
if "%ANTHROPIC_API_KEY%"=="" (
    echo.
    echo [!] No ANTHROPIC_API_KEY environment variable found.
    echo [!] You can set it via the Settings button in the app,
    echo [!] or edit config.py directly, or set the env variable:
    echo.
    echo     setx ANTHROPIC_API_KEY "your-key-here"
    echo.
)

echo [*] Launching JARVIS...
echo.
python main.py

pause
