@echo off
title Haven Extractor - Update Checker
echo.
echo   Checking for Haven Extractor updates...
echo.

cd /d "%~dp0"

REM Verify PowerShell is available (ships with Windows 10/11)
where powershell >nul 2>&1
if errorlevel 1 (
    echo ERROR: PowerShell is required for auto-update.
    echo PowerShell comes pre-installed on Windows 10 and 11.
    pause
    exit /b 1
)

REM Run the update script
powershell -ExecutionPolicy Bypass -NoProfile -File "%~dp0haven_updater.ps1"

echo.
pause
