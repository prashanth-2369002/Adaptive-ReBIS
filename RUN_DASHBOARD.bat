@echo off
cd /d "%~dp0"
echo Starting Adaptive-ReBIS dashboard... (close this window to stop)
py -m streamlit run dashboardpp.py --browser.gatherUsageStats false
pause
