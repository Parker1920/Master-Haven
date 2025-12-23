@echo off
REM Run the Haven Web UI (Windows batch wrapper) - robust path handling
pushd %~dp0\..
SET REPO_ROOT=%CD%
popd
SET PYTHONPATH=%REPO_ROOT%\src
SET HAVEN_UI_DIR=%~dp0
echo Starting Haven Control Room API with REPO_ROOT=%REPO_ROOT% PYTHONPATH=%PYTHONPATH% HAVEN_UI_DIR=%HAVEN_UI_DIR%

REM Use system python (venv has issues)
echo Using system python
mkdir Haven-UI\logs 2>nul
start /B "python" python -m uvicorn src.control_room_api:app --host 0.0.0.0 --port 8005 > Haven-UI\logs\run_server.out.log 2> Haven-UI\logs\run_server.err.log
