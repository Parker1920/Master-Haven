@echo off
echo ========================================
echo  MASTER HAVEN - COMPLETE STARTUP
echo ========================================
echo.

REM Start Haven UI (Backend + Frontend)
echo [1/2] Starting Haven UI...
start "Haven UI" cmd /k "cd Haven-UI && npm run dev"
timeout /t 3 /nobreak >nul

REM Start Keeper Discord Bot
echo [2/2] Starting Keeper Bot...
start "Keeper Bot" cmd /k "cd keeper-discord-bot-main && python src/main.py"

echo.
echo ========================================
echo  ALL SERVICES STARTED!
echo ========================================
echo.
echo Haven UI: http://localhost:5173
echo Haven API: http://localhost:8005
echo Keeper Bot: Running in separate window
echo.
echo Press any key to exit this window...
pause >nul
