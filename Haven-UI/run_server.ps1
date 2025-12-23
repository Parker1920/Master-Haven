<#
Run the Haven-UI server from PowerShell
This script sets PYTHONPATH and HAVEN_UI_DIR, selects the venv python if present, and runs uvicorn.
Usage: Run this from PowerShell in the Haven-UI folder or as an absolute path.
#>
param(
  [string]$HostName = '127.0.0.1',
  [int]$Port = 8000,
  [switch]$Reload
)

$repoRoot = Split-Path -Parent $PSScriptRoot
Write-Host "Repo root: $repoRoot"
$env:PYTHONPATH = Join-Path $repoRoot 'src'
$env:HAVEN_UI_DIR = Join-Path $repoRoot 'Haven-UI'

$venvPython = Join-Path $repoRoot '.venv\Scripts\python.exe'
if (Test-Path $venvPython) {
  Write-Host "Using venv python: $venvPython"
  $python = $venvPython
} else {
  Write-Host "Using system python"
  $python = "python"
}

Write-Host "Starting Haven Control Room API on http://$($HostName):$($Port)"
$args = "-m uvicorn src.control_room_api:app --host $HostName --port $Port --log-level info"
if ($Reload) { $args += " --reload" }
Write-Host "Running: $python $args"

# Ensure logs folder exists
$uiDir = Join-Path -Path $repoRoot -ChildPath 'Haven-UI'
$logDir = Join-Path -Path $uiDir -ChildPath 'logs'
if (-not (Test-Path $logDir)) { New-Item -ItemType Directory -Path $logDir | Out-Null }
$outLog = Join-Path -Path $logDir -ChildPath 'run_server.out.log'
$errLog = Join-Path -Path $logDir -ChildPath 'run_server.err.log'

# Launch process and capture PID
$proc = Start-Process -FilePath $python -ArgumentList $args -RedirectStandardOutput $outLog -RedirectStandardError $errLog -PassThru -WindowStyle Hidden
Write-Host "Server process launched (PID: $($proc.Id)). Logs: $outLog, $errLog"

# Save PID to file
$pidFile = Join-Path -Path $uiDir -ChildPath 'run_server.pid'
$proc.Id | Out-File -FilePath $pidFile -Encoding ascii
