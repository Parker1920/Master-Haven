@echo off
echo ==========================================
echo  Haven Extractor v7.3.0 - Installation
echo ==========================================
echo.

set "SOURCE=%~dp0haven_extractor.py"
set "DEST=C:\Program Files (x86)\Steam\steamapps\common\No Man's Sky\GAMEDATA\MODS"

echo Source: %SOURCE%
echo Dest:   %DEST%
echo.

if not exist "%SOURCE%" (
    echo ERROR: haven_extractor.py not found!
    pause
    exit /b 1
)

if not exist "%DEST%" (
    echo Creating MODS directory...
    mkdir "%DEST%"
)

echo Copying haven_extractor.py to NMS MODS folder...
copy /Y "%SOURCE%" "%DEST%\haven_extractor.py"

if errorlevel 1 (
    echo.
    echo ERROR: Copy failed! Try running as Administrator.
    pause
    exit /b 1
)

echo.
echo ==========================================
echo  SUCCESS! Haven Extractor v7.3.0 installed.
echo ==========================================
echo.
echo DEBUG VERSION - Testing freighter scanner room hooks
echo.
echo Debug hooks enabled (logging only):
echo   - cGcScanEvent.Construct.after
echo   - cGcPlayerDiscoveryHelper.GetDiscoveryWorth.after
echo.
echo Use the freighter scanner room and check NMS logs to see which hook fires!
echo.
echo To run NMS with pyMHF:
echo   "%USERPROFILE%\AppData\Local\Programs\Python\Python311\Scripts\pymhf.exe" run nmspy
echo.
echo Output will be saved to:
echo   %USERPROFILE%\Documents\Haven-Extractor\
echo.
pause
