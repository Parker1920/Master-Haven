<#
deploy_to_pi.ps1

Small helper/instructions to upload the update bundle to a Raspberry Pi and apply it.

USAGE (dry-run):
  powershell -ExecutionPolicy Bypass -File .\scripts\deploy_to_pi.ps1 -Host 10.0.0.33 -User parker

USAGE (interactive):
  powershell -ExecutionPolicy Bypass -File .\scripts\deploy_to_pi.ps1 -Host 10.0.0.33 -User parker -DoDeploy

This script does NOT attempt to guess how your server is run on the Pi (systemd, screen, tmux, etc.).
It uploads an archive to /tmp, extracts into the repo, and prints the exact commands to restart services.
#>

param(
  [Alias('Host')][Parameter(Mandatory=$true)] [string]$RemoteHost,
    [Parameter(Mandatory=$true)] [string]$User,
    [string]$RemotePath = '/home/parker/Master-Haven',
    [string]$Archive = 'Master-Haven-update.tar.gz',
    [switch]$DoDeploy
)

if (-not (Test-Path $Archive)) {
    Write-Host "Archive $Archive not found. Run scripts\create_update_archive.ps1 first." -ForegroundColor Yellow
    exit 2
}

Write-Host "DEPLOY PLAN" -ForegroundColor Cyan
$dest = $User + '@' + $RemoteHost + ':/tmp/' + $Archive
Write-Host "  Upload: $Archive -> $dest"
Write-Host "  Extract into: $RemotePath"
Write-Host "  NOTE: This does not automatically restart system services. See restart suggestions below."

$upload = "scp $Archive $dest"
Write-Host "Upload command: `n  $upload`n"

  $apply = @"
ssh $dest << 'SSH'
  set -e
  # Make backup (best-effort)
  TIMESTAMP=$(date +%Y%m%d_%H%M%S)
  BACKUP_DIR=$RemotePath-backup-$TIMESTAMP
  echo "Creating backup: $BACKUP_DIR"
  cp -a $RemotePath $BACKUP_DIR || echo 'backup failed — continuing'
  # Extract archive into repo
  tar -xzf /tmp/$Archive -C /tmp
  rsync -av --delete /tmp/Master-Haven/ $RemotePath/
  echo 'Files updated. Please restart the Haven UI server on the Pi.'
SSH
"@

Write-Host "Remote apply commands: `n$apply`n"

Write-Host "RESTART SUGGESTIONS (pick whichever matches your Pi setup):" -ForegroundColor Cyan
Write-Host " - If systemd unit is used: sudo systemctl restart haven-ui.service" -ForegroundColor Gray
Write-Host " - If you run with a screen/tmux session: attach it and restart python server (python3 server.py)" -ForegroundColor Gray
Write-Host " - Or run: cd $RemotePath/Haven-UI && source ../.venv/bin/activate && python3 server.py" -ForegroundColor Gray

if ($DoDeploy) {
    Write-Host "Uploading archive now..." -ForegroundColor Cyan
    $scpCmd = "scp $Archive $dest"
    $scpProc = Start-Process -FilePath scp -ArgumentList "$Archive $dest" -NoNewWindow -Wait -PassThru
    if ($scpProc.ExitCode -ne 0) { Write-Host "SCP failed (exit $($scpProc.ExitCode))" -ForegroundColor Red; exit $scpProc.ExitCode }
    Write-Host "Archive uploaded. Now applying remote commands..." -ForegroundColor Cyan
    Write-Host "Note: This will open an SSH session and execute remote steps."
    Invoke-Expression $apply
}
