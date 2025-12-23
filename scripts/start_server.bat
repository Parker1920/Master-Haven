@echo off
REM Simple script to start the Haven Control Room API server
REM This runs in the foreground so you can see the logs directly

cd /d "%~dp0.."
echo Starting Haven Control Room API...
echo Server will run on http://localhost:8000
echo Press Ctrl+C to stop the server
echo.

.venv\Scripts\python.exe src\control_room_api.py
