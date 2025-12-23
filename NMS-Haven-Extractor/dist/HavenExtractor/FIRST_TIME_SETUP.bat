@echo off
title Haven Extractor - First Time Setup
echo ============================================================
echo   HAVEN EXTRACTOR - First Time Setup
echo ============================================================
echo.

cd /d "%~dp0"

if not exist "python\python.exe" (
    echo ERROR: Embedded Python not found!
    pause
    exit /b 1
)

echo Verifying installation...
python\python.exe -c "import nmspy; print('nmspy:', nmspy.__version__)"
python\python.exe -c "import pymhf; print('pymhf:', pymhf.__version__)"

echo.
echo If you see version numbers above, the installation is correct!
echo.
echo You can now run RUN_HAVEN_EXTRACTOR.bat to start extracting.
echo.
pause
