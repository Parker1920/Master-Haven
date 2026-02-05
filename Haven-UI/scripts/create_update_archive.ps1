param(
    [string]$OutFile = "Master-Haven-update.tar.gz",
    [string[]]$Include = @(
        'src/control_room_api.py',
        'Haven-UI/server.py',
        'scripts/ngrok_check.ps1',
        'docs/PI-DEPLOYMENT-GUIDE.md'
    )
)

Write-Host "Creating update archive: $OutFile"
$items = $Include | ForEach-Object { "`"$_`"" }

# Use tar if available (Windows 10+ ships with tar)
$cmd = "tar -czf $OutFile " + ($Include -join ' ')
Write-Host $cmd
& tar -czf $OutFile @Include

if ($LASTEXITCODE -eq 0) {
    Write-Host "Archive created: $OutFile" -ForegroundColor Green
} else {
    Write-Host "Failed to create archive (exit code $LASTEXITCODE)" -ForegroundColor Red
    exit $LASTEXITCODE
}
