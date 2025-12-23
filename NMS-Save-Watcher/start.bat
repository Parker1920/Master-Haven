@echo off
title NMS Save Watcher
cd /d "%~dp0"

REM Check if Python is available
python --version >nul 2>&1
if errorlevel 1 (
    echo Python is not installed or not in PATH
    echo Please install Python 3.10+ from https://python.org
    pause
    exit /b 1
)

REM Check if venv exists, create if not
if not exist "venv" (
    echo Creating virtual environment...
    python -m venv venv
)

REM Activate venv
call venv\Scripts\activate.bat

REM Install/upgrade dependencies
echo Checking dependencies...
pip install -q -r requirements.txt

REM Run the application
echo.
python -m src

REM Keep window open if there was an error
if errorlevel 1 (
    echo.
    echo Application exited with error.
    pause
)
