@echo off
REM Expense Tracker — Launch App (after first-time setup)
REM Double-click this file on Windows to start the app.

cd /d "%~dp0"
python setup\setup.py --launch
pause
