@echo off
title Haven Extractor v9.0.0 - DEBUG MODE
echo ============================================================
echo   HAVEN EXTRACTOR v9.0.0 - DEBUG MODE
echo ============================================================
echo.

REM Change to the script directory
cd /d "%~dp0"
echo Current directory: %CD%
echo.

REM Check if Python is available
echo Checking for embedded Python...
if not exist "python\python.exe" (
    echo ERROR: python\python.exe not found!
    echo.
    echo Contents of current directory:
    dir /b
    echo.
    pause
    exit /b 1
)
echo FOUND: python\python.exe
echo.

REM Check if mod folder exists
echo Checking for mod folder...
if not exist "mod\haven_extractor.py" (
    echo ERROR: mod\haven_extractor.py not found!
    echo.
    echo Contents of mod folder:
    dir /b mod 2>nul || echo (mod folder does not exist)
    echo.
    pause
    exit /b 1
)
echo FOUND: mod\haven_extractor.py
echo.

REM Test Python works
echo Testing Python...
python\python.exe --version
if errorlevel 1 (
    echo ERROR: Python failed to run!
    pause
    exit /b 1
)
echo.

REM Test pymhf import
echo Testing pymhf import...
python\python.exe -c "print('Testing imports...'); import pymhf; print('pymhf OK')"
if errorlevel 1 (
    echo.
    echo ERROR: pymhf import failed!
    echo This usually means pymhf is not installed or has missing dependencies.
    echo.
    pause
    exit /b 1
)
echo.

REM Test nmspy import
echo Testing nmspy import...
python\python.exe -c "import nmspy; print('nmspy OK, version:', nmspy.__version__)"
if errorlevel 1 (
    echo.
    echo ERROR: nmspy import failed!
    pause
    exit /b 1
)
echo.

echo ============================================================
echo All checks passed! Ready to start.
echo ============================================================
echo.
echo Press any key to start the extractor...
pause > nul

REM Add embedded Python to PATH
set "PATH=%~dp0python;%~dp0python\Scripts;%PATH%"

REM Run pymhf
cd mod
echo.
echo Running pymhf...
echo.
..\python\python.exe -c "import sys; sys.argv = ['pymhf', 'run', '.']; from pymhf import run; run()"

echo.
echo ============================================================
echo Extractor finished. Exit code: %errorlevel%
echo ============================================================
pause
