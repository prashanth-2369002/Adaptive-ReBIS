@echo off
cd /d "%~dp0"
py run_all.py
py src\make_summary.py
pause
