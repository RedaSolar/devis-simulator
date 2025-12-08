@echo off
cd /d "C:\Users\kasri\OneDrive - Atlencia\Solar Panels\Simulator"

echo Netoyage du cache Streamlit...
streamlit cache clear

echo Lancement de l'application...
streamlit run app_old.py
pause
