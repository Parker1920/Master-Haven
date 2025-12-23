@echo off
echo ============================================
echo Starting Master Haven - Keeper Discord Bot
echo ============================================
echo.
echo Bot will connect to Discord...
echo Press Ctrl+C to stop
echo.

cd /d "%~dp0..\keeper-discord-bot-main"
.venv\Scripts\python src\main.py

pause
