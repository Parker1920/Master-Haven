<#
ngrok_check.ps1

Simple diagnostic helper for checking a local ngrok tunnel and TLS from the host.
Place this file in the repository and run in PowerShell while you reproduce a failure.

Usage: 
  powershell -ExecutionPolicy Bypass -File .\scripts\ngrok_check.ps1

What it does:
 - Calls ngrok web API at http://127.0.0.1:4040 to list tunnels
 - Tests the HTTPS forwarding URL with Invoke-WebRequest (shows status, headers)
 - Shows a short checklist for debugging mobile TLS issues
#>

param(
    [string]$TunnelApi = 'http://127.0.0.1:4040/api/tunnels',
    [int]$TimeoutSeconds = 10
)

function Show-Heading($text) { Write-Host "`n==== $text ====`n" -ForegroundColor Cyan }

Show-Heading "ngrok diagnostics"

try {
    $tunnels = Invoke-RestMethod -Uri $TunnelApi -ErrorAction Stop -TimeoutSec $TimeoutSeconds
} catch {
    Write-Host "Could not reach ngrok API at $TunnelApi. Is ngrok running and web inspector enabled?" -ForegroundColor Yellow
    Write-Host "If not, start ngrok with: ngrok http 8005 --log=stdout" -ForegroundColor Gray
    exit 2
}

if ($tunnels.tunnels.Count -eq 0) {
    Write-Host "No tunnels found." -ForegroundColor Yellow
    exit 3
}

foreach ($t in $tunnels.tunnels) {
    Write-Host "Name: $($t.name)" -ForegroundColor Green
    Write-Host "Forwarding: $($t.public_url) -> $($t.config.addr)" -ForegroundColor Green
}

$public = $tunnels.tunnels[0].public_url
Show-Heading "Testing HTTPS connectivity to $public"

try {
    $resp = Invoke-WebRequest -Uri "$public/health" -UseBasicParsing -TimeoutSec $TimeoutSeconds
    Write-Host "Status: $($resp.StatusCode)" -ForegroundColor Green
    Write-Host "Content (first 256 chars):`n$($resp.Content.Substring(0,[Math]::Min(256,$resp.Content.Length)))`n"
} catch {
    Write-Host "HTTPS test failed locally. Error:`n$($_.Exception.Message)" -ForegroundColor Red
    Write-Host "Try restarting ngrok and the local server, or check the ngrok web UI: http://127.0.0.1:4040" -ForegroundColor Yellow
}

Show-Heading "Quick checklist (mobile client fails while hosts work)"
Write-Host " - If the host shows OK but the phone fails, try these on the phone:" -ForegroundColor Gray
Write-Host "   1) Ensure phone Date & Time are set to network time" -ForegroundColor Gray
Write-Host "   2) Disable any VPN, or set Private DNS to Automatic/Off temporarily" -ForegroundColor Gray
Write-Host "   3) Clear site data in Chrome, or test in Incognito / Firefox" -ForegroundColor Gray
Write-Host "   4) Check the ngrok dashboard for real-time request logs: http://127.0.0.1:4040" -ForegroundColor Gray

Show-Heading "To collect more info (advanced)"
Write-Host " - For TLS debugging: run on host:`n    openssl s_client -showcerts -connect $(($public.TrimStart('https://'))):443 -servername $(($public.TrimStart('https://')))" -ForegroundColor Gray
Write-Host " - For Android remote debugging: open chrome://inspect in desktop Chrome and connect phone via USB" -ForegroundColor Gray

Write-Host "Diagnostics complete." -ForegroundColor Cyan
exit 0