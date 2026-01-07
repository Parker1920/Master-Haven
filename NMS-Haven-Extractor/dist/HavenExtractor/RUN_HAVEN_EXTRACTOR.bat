@echo off
title Haven Extractor v9.0.0
echo ============================================================
echo   HAVEN EXTRACTOR v9.0.0 - Batch Mode
echo   For No Man's Sky
echo ============================================================
echo.

REM Change to the script directory
cd /d "%~dp0"

REM Check if Python is available
if not exist "python\python.exe" (
    echo ERROR: Embedded Python not found!
    echo Please ensure the package was extracted correctly.
    pause
    exit /b 1
)

REM API URL is hardcoded in the mod - always enabled!
echo API Config: HARDCODED - voyagers-haven-3dmap.ngrok.io
echo Remote sync is enabled by default!
echo.

echo Starting Haven Extractor...
echo.
echo This will:
echo   1. Start No Man's Sky
echo   2. Inject the Haven Extractor mod
echo   3. Warp to systems - data captured automatically!
echo   4. Click "Export Batch" to save all systems
echo.
echo Press any key to continue or Ctrl+C to cancel...
pause > nul

REM Add embedded Python to PATH so pymhf subprocesses can find it
set "PATH=%~dp0python;%~dp0python\Scripts;%PATH%"

REM Run pymhf by invoking its run function directly (pymhf.exe has hardcoded paths)
cd mod
..\python\python.exe -c "import sys; sys.argv = ['pymhf', 'run', '.']; from pymhf import run; run()"

echo.
echo Haven Extractor has finished.
pause
