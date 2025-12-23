@echo off
title Build NMS Save Watcher
cd /d "%~dp0"

REM Activate venv
if exist "venv\Scripts\activate.bat" (
    call venv\Scripts\activate.bat
) else (
    echo Creating virtual environment...
    python -m venv venv
    call venv\Scripts\activate.bat
)

REM Install build dependencies
echo Installing dependencies...
pip install -q -r requirements.txt
pip install -q pyinstaller

REM Clean previous build
echo Cleaning previous build...
if exist "build" rmdir /s /q build
if exist "dist" rmdir /s /q dist

REM Build with PyInstaller
echo Building executable...
pyinstaller nms_watcher.spec

if exist "dist\NMS-Save-Watcher.exe" (
    echo.
    echo Build successful!
    echo Output: dist\NMS-Save-Watcher.exe

    REM Copy config template
    copy /y config.json.example dist\config.json >nul 2>&1

    echo.
    echo To distribute, copy the entire 'dist' folder.
) else (
    echo.
    echo Build failed!
)

pause
