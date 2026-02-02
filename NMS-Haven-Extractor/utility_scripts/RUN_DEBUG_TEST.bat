@echo off
echo ==========================================
echo  Haven Extractor - Fractal413 Debug Test
echo ==========================================
echo.
echo This tool tests offset verification on the
echo NMS 4.13 DEBUG version (Fractal413).
echo.
echo REQUIREMENTS:
echo   - Fractal413 installed
echo   - RunAsDate configured (date before Sept 28, 2023)
echo   - pyMHF installed
echo.

REM Check if pyMHF mods folder exists
set PYMHF_MODS=%USERPROFILE%\.pymhf\mods
if not exist "%PYMHF_MODS%" (
    echo Creating pyMHF mods folder...
    mkdir "%PYMHF_MODS%"
)

echo Copying debug test mod to pyMHF mods folder...
copy /Y "%~dp0debug_offset_test.py" "%PYMHF_MODS%\debug_offset_test.py"

if errorlevel 1 (
    echo ERROR: Failed to copy debug test mod!
    pause
    exit /b 1
)

echo.
echo ==========================================
echo  DEBUG TEST MOD INSTALLED!
echo ==========================================
echo.
echo Output folder:
echo   %USERPROFILE%\Documents\Haven-Extractor\debug_tests\
echo.
echo ==========================================
echo  HOW TO USE FRACTAL413:
echo ==========================================
echo.
echo 1. Open RunAsDate (download from NirSoft if needed)
echo    - Set date to September 27, 2023 or earlier
echo    - Point it to your Fractal413 NMS.exe
echo.
echo 2. OR use this command (adjust path as needed):
echo    RunAsDate.exe /movetime "27\09\2023 12:00:00" ^
echo    "C:\Users\parke\OneDrive\Desktop\Fractal413\Binaries\NMS.exe"
echo.
echo 3. Launch NMS through RunAsDate, then attach pyMHF:
echo    pymhf --attach NMS.exe
echo.
echo 4. Load your save and enter a solar system
echo    Results saved to the output folder above
echo.
echo ==========================================
pause
