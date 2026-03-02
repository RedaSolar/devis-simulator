@echo off
title TAQINOR Solar Quote Simulator
cd /d "%~dp0"

echo Stopping any existing server on port 8000...
for /f "tokens=5" %%a in ('netstat -aon 2^>nul ^| findstr ":8000 " ^| findstr LISTENING') do (
    taskkill /F /PID %%a >nul 2>&1
)
timeout /t 1 /nobreak >nul

echo =========================================
echo   TAQINOR Solar Quote Simulator
echo   Opening at http://localhost:8000
echo   Press CTRL+C to stop.
echo =========================================
echo.

start "" http://localhost:8000
python -m uvicorn main:app --host 127.0.0.1 --port 8000
pause
