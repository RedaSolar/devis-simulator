@echo off
title TAQINOR Server
cd /d "%~dp0"

echo Stopping any existing server on port 8000...
for /f "tokens=5" %%a in ('netstat -aon 2^>nul ^| findstr ":8000 " ^| findstr LISTENING') do (
    taskkill /F /PID %%a >nul 2>&1
)
timeout /t 2 /nobreak >nul

echo =========================================
echo   TAQINOR Solar Quote Simulator
echo   http://localhost:8000
echo   Code changes reload automatically.
echo   Press CTRL+C to stop.
echo =========================================

set WATCHFILES_FORCE_POLLING=true
python -m uvicorn main:app --host 0.0.0.0 --port 8000 --reload --reload-delay 1
pause
