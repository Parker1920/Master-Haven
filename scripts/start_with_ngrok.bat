@echo off
setlocal enabledelayedexpansion

REM start_with_ngrok.bat
REM Opens two Command Prompt windows:
REM  1) Runs ngrok and keeps the window open
REM  2) Starts the Haven Control Room server (via run_server.bat) and keeps the window open
REM
REM Usage: double-click this file or run from an existing cmd: start_with_ngrok.bat

:: Calculate the repo root (script lives in scripts folder)
pushd %~dp0..
set REPO_ROOT=%CD%
popd

:: Config
set NGROK_PORT=8005
set NGROK_CMD=ngrok
set HAVEN_UI_DIR=%REPO_ROOT%\Haven-UI

echo Repo root: %REPO_ROOT%
echo Starting ngrok and Haven server in separate windows...

:: Check ngrok availability
where %NGROK_CMD% >nul 2>nul
if errorlevel 1 (
  echo WARNING: ngrok executable not found in PATH.
  echo You can download it from https://ngrok.com and add it to your PATH.
  echo Press any key to continue and attempt to start the server only, or close this window to abort.
  pause >nul
  goto :START_SERVER_ONLY
)

:: Start ngrok in a new cmd window and keep the window open (/k)
start "ngrok" cmd.exe /k "cd /d %REPO_ROOT% && %NGROK_CMD% http %NGROK_PORT% --log=stdout"

:START_SERVER_ONLY
:: Start the Haven UI server in a new cmd window and keep it open
:: If a PID file exists and process is running, just open a window showing the PID
set PID_FILE=%HAVEN_UI_DIR%\run_server.pid
if exist "%PID_FILE%" (
  for /f "usebackq delims=\r\n" %%p in ("%PID_FILE%") do set RUN_PID=%%p
  if defined RUN_PID (
    for /f "tokens=1" %%A in ('tasklist /FI "PID eq %RUN_PID%" ^| findstr /R "%RUN_PID%"') do set FOUND=%%A
    if defined FOUND (
      start "Haven Server" cmd.exe /k "echo Haven server already running (PID: %RUN_PID%) && cd /d %REPO_ROOT% && pause"
      goto :END
    )
  )
)

:: No running server detected — start a new one
start "Haven Server" cmd.exe /k "cd /d %REPO_ROOT% && call Haven-UI\run_server.bat"

:END
echo Launched ngrok (if available) and the Haven Server in separate windows.
pause
endlocal
exit /b 0
