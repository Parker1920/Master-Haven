@echo off
echo ============================================
echo Starting Master Haven - Haven UI
echo ============================================
echo.
echo Server will start on http://localhost:8005
echo Press Ctrl+C to stop
echo.

cd /d "%~dp0"
Haven-UI\.venv\Scripts\python src\control_room_api.py

pause
