@echo off
echo ================================================
echo  Haven Watcher - First Time Setup
echo ================================================
echo.

REM Check if Python is installed
python --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python is not installed or not in PATH
    echo Please install Python 3.11+ from https://python.org
    echo Make sure to check "Add Python to PATH" during installation
    pause
    exit /b 1
)

echo [*] Python found:
python --version
echo.

REM Remove old venv if it exists
if exist "venv" (
    echo [*] Removing old virtual environment...
    rmdir /s /q venv
)

REM Create new venv
echo [*] Creating virtual environment...
python -m venv venv
if errorlevel 1 (
    echo [ERROR] Failed to create virtual environment
    pause
    exit /b 1
)

echo [*] Activating virtual environment...
call venv\Scripts\activate.bat

echo [*] Installing dependencies...
pip install -r requirements.txt
if errorlevel 1 (
    echo [ERROR] Failed to install dependencies
    pause
    exit /b 1
)

echo.
echo ================================================
echo  Setup Complete!
echo ================================================
echo.
echo To run the watcher:
echo   1. Double-click RUN_WATCHER.bat
echo   OR
echo   2. Run: venv\Scripts\python.exe -m src
echo.
pause
