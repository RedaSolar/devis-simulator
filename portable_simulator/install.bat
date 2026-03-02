@echo off
title TAQINOR - Installation
cd /d "%~dp0"

echo =========================================
echo   TAQINOR Solar Quote Simulator
echo   First-time setup
echo =========================================
echo.

echo [1/3] Installing Python dependencies...
pip install -r requirements.txt
if errorlevel 1 (
    echo ERROR: pip install failed. Make sure Python 3.9+ is installed.
    pause
    exit /b 1
)

echo.
echo [2/3] Installing Playwright browser (Chromium)...
python -m playwright install chromium
if errorlevel 1 (
    echo ERROR: Playwright install failed.
    pause
    exit /b 1
)

echo.
echo [3/3] Setup complete!
echo.
echo You can now run start.bat to launch the simulator.
echo.
pause
