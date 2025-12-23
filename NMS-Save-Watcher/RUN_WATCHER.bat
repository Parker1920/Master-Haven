@echo off
cd /d "%~dp0"

if not exist "venv\Scripts\python.exe" (
    echo [ERROR] Virtual environment not found!
    echo Please run SETUP.bat first.
    pause
    exit /b 1
)

echo Starting Haven Watcher...
venv\Scripts\python.exe -m src
pause
