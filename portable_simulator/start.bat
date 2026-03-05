@echo off
echo Demarrage du Simulateur TAQINOR...
start http://localhost:8000
uvicorn main:app --host 0.0.0.0 --port 8000
pause
