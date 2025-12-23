param(
  [switch]$Build,
  [int]$Port = 8002,
  [string]$ServerHost = '127.0.0.1'
)

# Preview script: optionally build the UI, start uvicorn, and open the browser to the SPA URL
$scriptRoot = Split-Path -Parent $MyInvocation.MyCommand.Definition
$repoRoot = Resolve-Path "$scriptRoot\..\.."
Write-Host "Repo root: $repoRoot"

if ($Build) {
  Write-Host "Building the UI (npm ci && npm run build)"
  Push-Location "$repoRoot\Haven-UI"
  npm ci
  npm run build
  # If static assets exist (icons) but not copied into dist, copy them for consistent preview
  $srcAssets = Join-Path $repoRoot 'Haven-UI\static\assets'
  $distAssets = Join-Path $repoRoot 'Haven-UI\dist\assets'
  if ((Test-Path $srcAssets) -and !(Test-Path $distAssets)) {
    New-Item -ItemType Directory -Path $distAssets -Force | Out-Null
  }
  if ((Test-Path $srcAssets) -and (Test-Path $distAssets)) {
    Get-ChildItem -Path $srcAssets -File | ForEach-Object { Copy-Item $_.FullName (Join-Path $distAssets $_.Name) -Force }
  }
  Pop-Location
}

Push-Location $repoRoot

$env:PYTHONPATH = "$(Join-Path $repoRoot 'src')"
$env:HAVEN_UI_DIR = "$(Join-Path $repoRoot 'Haven-UI')"

# Avoid $Host (PowerShell builtin) - use $ServerHost for host name
$portStr = "{0}:{1}" -f $ServerHost, $Port
Write-Host ("Starting server on http://{0} (uvicorn)" -f $portStr)

# Start server in the background and return PID
$arg = "-u -m uvicorn src.control_room_api:app --host {0} --port {1} --log-level info" -f $ServerHost, $Port
$uvicorn = Start-Process -FilePath python -ArgumentList $arg -NoNewWindow -PassThru
Write-Host "Server process started (PID: $($uvicorn.Id))"

# Save PID for convenience
Set-Content -Path "$repoRoot\Haven-UI\scripts\preview.pid" -Value $uvicorn.Id -Force

# Wait up to 30 seconds for server to respond
 $url = 'http://' + $ServerHost + ':' + $Port + '/haven-ui/'
$i = 0
while ($i -lt 30) {
  try {
    $r = Invoke-WebRequest -UseBasicParsing -Uri $url -TimeoutSec 2 -ErrorAction Stop
    if ($r.StatusCode -eq 200) {
      Write-Host "Server is up — opening browser at $url"
      Start-Process "$url"
      break
    }
  } catch {
    Start-Sleep -Seconds 1
  }
  $i = $i + 1
}

if (($i -eq 29) -or (-not $r)) {
  Write-Warning "Server did not respond in 30s — check logs or run uvicorn manually with the provided env variables"
  Write-Host "To stop, run: Stop-Process -Id $($uvicorn.Id)"
}

Pop-Location

Write-Host "Preview started (PID: $($uvicorn.Id)). To stop: Stop-Process -Id $($uvicorn.Id)"
