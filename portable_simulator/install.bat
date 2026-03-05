@echo off
echo Installation du Simulateur TAQINOR...
pip install -r requirements.txt
python -m playwright install chromium
echo Installation terminee!
pause
