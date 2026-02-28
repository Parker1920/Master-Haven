@echo off
title Haven Extractor v1.5.1 - First Time Setup
echo ============================================================
echo   HAVEN EXTRACTOR v1.5.1 - Installation Verification
echo ============================================================
echo.

cd /d "%~dp0"

echo [1/6] Checking Python installation...
if not exist "python\python.exe" (
    echo ERROR: Embedded Python not found!
    echo Make sure you extracted the ENTIRE folder, not just some files.
    pause
    exit /b 1
)
echo       Python found!

echo.
echo [2/6] Testing Python works...
python\python.exe --version
if errorlevel 1 (
    echo ERROR: Python failed to run!
    pause
    exit /b 1
)

echo.
echo [3/6] Checking mod files...
if not exist "mod\haven_extractor.py" (
    echo ERROR: mod\haven_extractor.py not found!
    pause
    exit /b 1
)
if not exist "mod\pymhf.toml" (
    echo ERROR: mod\pymhf.toml not found!
    pause
    exit /b 1
)
echo       All mod files present!

echo.
echo [4/6] Testing nmspy import...
python\python.exe -c "import nmspy; print('       nmspy version:', nmspy.__version__)"
if errorlevel 1 (
    echo ERROR: nmspy import failed!
    pause
    exit /b 1
)

echo.
echo [5/6] Testing pymhf import...
python\python.exe -c "import pymhf; print('       pymhf version:', pymhf.__version__)"
if errorlevel 1 (
    echo ERROR: pymhf import failed!
    pause
    exit /b 1
)

echo.
echo [6/6] Checking output directory...
python\python.exe -c "import pathlib; p = pathlib.Path.home() / 'Documents' / 'Haven-Extractor'; print('       Output will go to:', p)"

echo.
echo ============================================================
echo   ALL CHECKS PASSED! Installation is correct.
echo ============================================================
echo.
echo You can now run RUN_HAVEN_EXTRACTOR.bat to start extracting.
echo.
echo QUICK GUIDE:
echo   1. Run RUN_HAVEN_EXTRACTOR.bat
echo   2. NMS will start with the mod loaded
echo   3. Warp to systems - data captured automatically!
echo   4. Click "Batch Status" to see collected systems
echo   5. Click "Export Batch" to save all data
echo.
pause
