@echo off
title NMS Memory Browser v3.8.5
REM ============================================================
REM NMS Memory Browser Launcher
REM This script launches the Memory Browser mod using pymhf
REM Must be run from a native Windows command prompt (cmd.exe)
REM ============================================================

echo ============================================================
echo   NMS MEMORY BROWSER v3.8.5 - Memory View Only
echo   For No Man's Sky
echo ============================================================
echo.

REM Change to the script directory
cd /d "%~dp0"
echo Working directory: %cd%
echo.

REM Check if Steam is running
tasklist /fi "imagename eq steam.exe" 2>nul | find /i "steam.exe" >nul
if errorlevel 1 (
    echo [WARNING] Steam does not appear to be running!
    echo Please start Steam before launching the mod.
    echo.
    echo Press any key to continue anyway or Ctrl+C to cancel...
    pause > nul
)

echo [OK] Steam detected
echo.

echo This will:
echo   1. Start No Man's Sky via Steam
echo   2. Inject the Memory Browser mod
echo   3. Open the Memory Browser GUI
echo.
echo Press any key to continue or Ctrl+C to cancel...
pause > nul
echo.

echo Starting pymhf...
echo.

REM Run pymhf - using sys.argv approach like Haven Extractor
REM This ensures proper argument handling
python -c "import sys; sys.argv = ['pymhf', 'run', '.']; from pymhf import run; run()"

if errorlevel 1 (
    echo.
    echo ============================================================
    echo [ERROR] pymhf failed to start!
    echo.
    echo Possible causes:
    echo   1. Python not installed or not in PATH
    echo   2. pymhf not installed: pip install pymhf
    echo   3. nmspy not installed: pip install nmspy
    echo   4. Steam not running
    echo   5. NMS not installed
    echo ============================================================
)

echo.
echo ============================================================
echo Memory Browser has finished.
echo ============================================================
pause
