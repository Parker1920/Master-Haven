<#
Stop the Haven UI server started by `run_server.ps1`.
Usage: powershell -ExecutionPolicy Bypass -File .\stop_server.ps1
#>
$repoRoot = Split-Path -Parent $PSScriptRoot
$pidFile = Join-Path $repoRoot 'Haven-UI' 'run_server.pid'
if (Test-Path $pidFile) {
  $pid = Get-Content $pidFile | Select-Object -First 1
  try {
    Stop-Process -Id $pid -Force -ErrorAction Stop
    Write-Host "Stopped process $pid"
    Remove-Item $pidFile -ErrorAction SilentlyContinue
  } catch {
    Write-Host "Failed to stop process $pid: $_"
  }
} else {
  Write-Host "PID file not found: $pidFile. No process stopped."
}
