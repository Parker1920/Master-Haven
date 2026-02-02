@echo off
setlocal enabledelayedexpansion
chcp 65001 >nul 2>&1
title Master Haven - Data Transfer to Raspberry Pi
color 0E

cls
echo.
echo    MASTER HAVEN - DATA TRANSFER TO RASPBERRY PI
echo    =============================================
echo.

cd /d "%~dp0"

REM =============================================
REM CONFIGURATION - Edit these values
REM =============================================
set "PI_USER=parker"
set "PI_HOST=10.0.0.33"
set "PI_PATH=/home/parker/Master-Haven"

REM =============================================
REM Prompt for Pi connection details
REM =============================================
echo    Current settings:
echo    -----------------------------------------
echo      Pi User: !PI_USER!
echo      Pi Host: !PI_HOST!
echo      Pi Path: !PI_PATH!
echo    -----------------------------------------
echo.
set /p "CHANGE_SETTINGS=    Change settings? (y/N): "
if /i "!CHANGE_SETTINGS!"=="y" (
    echo.
    set /p "PI_USER=    Enter Pi username [!PI_USER!]: "
    set /p "PI_HOST=    Enter Pi hostname/IP [!PI_HOST!]: "
    set /p "PI_PATH=    Enter destination path [!PI_PATH!]: "
)

echo.
echo    Using: !PI_USER!@!PI_HOST!:!PI_PATH!
echo.
echo    =============================================
echo    SELECT TRANSFER OPTIONS
echo    =============================================
echo.
echo    What would you like to transfer?
echo.
echo      [1] Database only (Haven-UI/data/*.db)
echo      [2] Photos only (Haven-UI/photos/)
echo      [3] Config files only (.env, config.json)
echo      [4] Everything (Database + Photos + Configs)
echo      [5] Custom selection
echo      [0] Exit
echo.
set /p "CHOICE=    Enter choice (1-5, 0 to exit): "

if "!CHOICE!"=="0" goto :end
if "!CHOICE!"=="1" (
    set "DO_DB=y"
    set "DO_PHOTOS=n"
    set "DO_CONFIGS=n"
    goto :run_transfers
)
if "!CHOICE!"=="2" (
    set "DO_DB=n"
    set "DO_PHOTOS=y"
    set "DO_CONFIGS=n"
    goto :run_transfers
)
if "!CHOICE!"=="3" (
    set "DO_DB=n"
    set "DO_PHOTOS=n"
    set "DO_CONFIGS=y"
    goto :run_transfers
)
if "!CHOICE!"=="4" (
    set "DO_DB=y"
    set "DO_PHOTOS=y"
    set "DO_CONFIGS=y"
    goto :run_transfers
)
if "!CHOICE!"=="5" (
    echo.
    echo    -----------------------------------------
    echo    [*] Custom selection
    echo    -----------------------------------------
    echo.
    set /p "DO_DB=    Transfer database? (Y/n): "
    set /p "DO_PHOTOS=    Transfer photos? (Y/n): "
    set /p "DO_CONFIGS=    Transfer configs? (Y/n): "
    goto :run_transfers
)

echo    Invalid choice. Please try again.
pause
goto :end

REM =============================================
REM RUN SELECTED TRANSFERS
REM =============================================

:run_transfers

REM --- DATABASE ---
if /i not "!DO_DB!"=="n" (
    echo.
    echo    -----------------------------------------
    echo    [*] Transferring database files...
    echo    -----------------------------------------
    echo.

    echo    [*] Creating remote directories...
    ssh !PI_USER!@!PI_HOST! "mkdir -p !PI_PATH!/Haven-UI/data"

    if exist "Haven-UI\data\haven_ui.db" (
        echo    [+] Transferring haven_ui.db...
        scp "Haven-UI\data\haven_ui.db" "!PI_USER!@!PI_HOST!:!PI_PATH!/Haven-UI/data/"
        if !errorlevel!==0 (
            echo    [OK] haven_ui.db transferred successfully
        ) else (
            echo    [FAIL] Failed to transfer haven_ui.db
        )
    ) else (
        echo    [!] haven_ui.db not found - skipping
    )

    for %%f in ("Haven-UI\data\*.db.backup") do (
        echo    [+] Transferring %%~nxf...
        scp "%%f" "!PI_USER!@!PI_HOST!:!PI_PATH!/Haven-UI/data/"
    )
)

REM --- PHOTOS ---
if /i not "!DO_PHOTOS!"=="n" (
    echo.
    echo    -----------------------------------------
    echo    [*] Transferring photos...
    echo    -----------------------------------------
    echo.

    echo    [*] Creating remote directories...
    ssh !PI_USER!@!PI_HOST! "mkdir -p !PI_PATH!/Haven-UI/photos"

    if exist "Haven-UI\photos" (
        echo    [+] Transferring photos folder...
        scp -r "Haven-UI\photos" "!PI_USER!@!PI_HOST!:!PI_PATH!/Haven-UI/"
        if !errorlevel!==0 (
            echo    [OK] Photos transferred successfully
        ) else (
            echo    [!] No photos found or transfer failed
        )
    ) else (
        echo    [!] Photos folder not found - skipping
    )
)

REM --- CONFIGS ---
if /i not "!DO_CONFIGS!"=="n" (
    echo.
    echo    -----------------------------------------
    echo    [*] Transferring config files...
    echo    -----------------------------------------
    echo.

    if exist ".env" (
        echo    [+] Transferring .env...
        scp ".env" "!PI_USER!@!PI_HOST!:!PI_PATH!/"
        echo    [OK] .env transferred
    ) else (
        echo    [!] .env not found - skipping
    )

    if exist "Haven-UI\.env" (
        echo    [+] Transferring Haven-UI/.env...
        scp "Haven-UI\.env" "!PI_USER!@!PI_HOST!:!PI_PATH!/Haven-UI/"
        echo    [OK] Haven-UI/.env transferred
    ) else (
        echo    [!] Haven-UI/.env not found - skipping
    )

    if exist "config.json" (
        echo    [+] Transferring config.json...
        scp "config.json" "!PI_USER!@!PI_HOST!:!PI_PATH!/"
        echo    [OK] config.json transferred
    ) else (
        echo    [!] config.json not found - skipping
    )

    ssh !PI_USER!@!PI_HOST! "mkdir -p !PI_PATH!/NMS-Save-Watcher"
    if exist "NMS-Save-Watcher\config.json" (
        echo    [+] Transferring NMS-Save-Watcher/config.json...
        scp "NMS-Save-Watcher\config.json" "!PI_USER!@!PI_HOST!:!PI_PATH!/NMS-Save-Watcher/"
        echo    [OK] NMS-Save-Watcher/config.json transferred
    ) else (
        echo    [!] NMS-Save-Watcher/config.json not found - skipping
    )
)

REM =============================================
REM COMPLETE
REM =============================================

echo.
echo    =============================================
echo    TRANSFER COMPLETE
echo    =============================================
echo.
echo    [*] Data transfer finished!
echo.
echo    Next steps on your Raspberry Pi:
echo    -----------------------------------------
echo      1. cd !PI_PATH!
echo      2. git pull
echo      3. python -m venv .venv
echo      4. source .venv/bin/activate
echo      5. pip install -r requirements.txt
echo      6. cd Haven-UI and run: npm install
echo      7. python src/control_room_api.py
echo    -----------------------------------------
echo.

:end
endlocal
pause
