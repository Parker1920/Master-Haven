# ============================================================
# Haven Extractor Auto-Updater
# Called by UPDATE_HAVEN_EXTRACTOR.bat
# Downloads mod-only updates from GitHub Releases
# ============================================================

$ErrorActionPreference = 'Stop'
$repoOwner = 'Parker1920'
$repoName = 'Master-Haven'
$extractorDir = Split-Path -Parent $MyInvocation.MyCommand.Path

Write-Host "============================================================"
Write-Host "  HAVEN EXTRACTOR - Update Checker"
Write-Host "============================================================"
Write-Host ""

# Ensure TLS 1.2 for GitHub API
[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12

# -------------------------------------------------------
# Step 1: Read current version from haven_extractor.py
# -------------------------------------------------------
$modFile = Join-Path $extractorDir 'mod\haven_extractor.py'
if (-not (Test-Path $modFile)) {
    Write-Host "ERROR: mod\haven_extractor.py not found!" -ForegroundColor Red
    Write-Host "Make sure you run this from the HavenExtractor folder."
    exit 1
}

$content = Get-Content $modFile -Raw
if ($content -match '__version__\s*=\s*"(\d+\.\d+\.\d+)"') {
    $currentVersion = [version]$Matches[1]
} else {
    Write-Host "ERROR: Could not read version from haven_extractor.py" -ForegroundColor Red
    exit 1
}

Write-Host "Current version: $currentVersion" -ForegroundColor Cyan
Write-Host "Checking for updates..."
Write-Host ""

# -------------------------------------------------------
# Step 2: Query GitHub Releases API
# -------------------------------------------------------
try {
    $headers = @{ 'User-Agent' = 'HavenExtractor-Updater' }
    $apiUrl = "https://api.github.com/repos/$repoOwner/$repoName/releases/latest"
    $release = Invoke-RestMethod -Uri $apiUrl -Headers $headers -TimeoutSec 10
} catch {
    $statusCode = $null
    if ($_.Exception.Response) {
        $statusCode = [int]$_.Exception.Response.StatusCode
    }
    if ($statusCode -eq 404) {
        Write-Host "No releases published yet." -ForegroundColor Yellow
        Write-Host "You are on the latest version."
    } else {
        Write-Host "ERROR: Could not reach GitHub." -ForegroundColor Red
        Write-Host "       $($_.Exception.Message)"
        Write-Host ""
        Write-Host "Check your internet connection and try again."
    }
    exit 1
}

# -------------------------------------------------------
# Step 3: Parse and compare versions
# -------------------------------------------------------
$latestTag = $release.tag_name -replace '^v', ''
try {
    $latestVersion = [version]$latestTag
} catch {
    Write-Host "ERROR: Could not parse version from release tag: $($release.tag_name)" -ForegroundColor Red
    exit 1
}

Write-Host "Latest version:  $latestVersion" -ForegroundColor Cyan
Write-Host ""

if ($currentVersion -ge $latestVersion) {
    Write-Host "You are already up to date!" -ForegroundColor Green
    exit 0
}

# -------------------------------------------------------
# Step 4: Find mod-only zip asset in release
# -------------------------------------------------------
$asset = $release.assets | Where-Object { $_.name -like 'HavenExtractor-mod-*' } | Select-Object -First 1
if (-not $asset) {
    Write-Host "No mod update package found in this release." -ForegroundColor Yellow
    Write-Host "Please download the full update manually from:"
    Write-Host "  $($release.html_url)" -ForegroundColor Cyan
    exit 1
}

$downloadUrl = $asset.browser_download_url
$fileSize = [math]::Round($asset.size / 1KB)

Write-Host "============================================================" -ForegroundColor Green
Write-Host "  Update available: $currentVersion --> $latestVersion" -ForegroundColor Green
Write-Host "  Download size: $fileSize KB"
Write-Host "============================================================" -ForegroundColor Green
Write-Host ""

# Show release notes (first 8 lines)
if ($release.body) {
    Write-Host "--- What's New ---" -ForegroundColor Yellow
    $release.body -split "`n" | Select-Object -First 8 | ForEach-Object {
        Write-Host "  $_"
    }
    Write-Host "------------------" -ForegroundColor Yellow
    Write-Host ""
}

# -------------------------------------------------------
# Step 5: Confirm with user
# -------------------------------------------------------
$confirm = Read-Host "Download and install update? (Y/N)"
if ($confirm -notmatch '^[Yy]') {
    Write-Host "Update cancelled." -ForegroundColor Yellow
    exit 0
}

Write-Host ""

# -------------------------------------------------------
# Step 6: Download update zip
# -------------------------------------------------------
Write-Host "Downloading update..." -ForegroundColor Cyan

$tempZip = Join-Path $env:TEMP "HavenExtractor-mod-update.zip"
try {
    Invoke-WebRequest -Uri $downloadUrl -OutFile $tempZip -Headers $headers -UseBasicParsing
} catch {
    Write-Host "ERROR: Download failed: $($_.Exception.Message)" -ForegroundColor Red
    exit 1
}

Write-Host "Download complete." -ForegroundColor Green

# -------------------------------------------------------
# Step 7: Backup current mod folder
# -------------------------------------------------------
Write-Host "Backing up current mod folder..."

$modDir = Join-Path $extractorDir 'mod'
$backupDir = Join-Path $extractorDir 'mod_backup'

if (Test-Path $backupDir) {
    Remove-Item $backupDir -Recurse -Force
}
Copy-Item -Path $modDir -Destination $backupDir -Recurse

# -------------------------------------------------------
# Step 8: Preserve user-specific files
# -------------------------------------------------------
$userFiles = @{}
$preserveNames = @('haven_config.json', 'config.json', 'adjective_cache.json')

foreach ($fileName in $preserveNames) {
    $filePath = Join-Path $modDir $fileName
    if (Test-Path $filePath) {
        $userFiles[$fileName] = [System.IO.File]::ReadAllBytes($filePath)
    }
}

# Also preserve communities cache (outside mod folder)
$commCachePath = Join-Path ([Environment]::GetFolderPath('MyDocuments')) 'Haven-Extractor\communities_cache.json'
# (communities cache is outside mod/ so it won't be touched by the update)

# -------------------------------------------------------
# Step 9: Extract update into mod folder
# -------------------------------------------------------
Write-Host "Installing update..." -ForegroundColor Cyan

$tempExtract = Join-Path $env:TEMP "HavenExtractor-mod-extract"
if (Test-Path $tempExtract) {
    Remove-Item $tempExtract -Recurse -Force
}

Expand-Archive -Path $tempZip -DestinationPath $tempExtract -Force

# Copy extracted files into mod folder (overwrites existing)
Get-ChildItem $tempExtract -Recurse -File | ForEach-Object {
    $relativePath = $_.FullName.Substring($tempExtract.Length + 1)
    $destPath = Join-Path $modDir $relativePath
    $destDir = Split-Path $destPath -Parent
    if (-not (Test-Path $destDir)) {
        New-Item -ItemType Directory -Path $destDir -Force | Out-Null
    }
    Copy-Item $_.FullName -Destination $destPath -Force
}

# -------------------------------------------------------
# Step 10: Restore user-specific files
# -------------------------------------------------------
foreach ($entry in $userFiles.GetEnumerator()) {
    $filePath = Join-Path $modDir $entry.Key
    [System.IO.File]::WriteAllBytes($filePath, $entry.Value)
}

# -------------------------------------------------------
# Step 11: Cleanup temp files
# -------------------------------------------------------
Remove-Item $tempZip -Force -ErrorAction SilentlyContinue
Remove-Item $tempExtract -Recurse -Force -ErrorAction SilentlyContinue

# -------------------------------------------------------
# Step 12: Verify new version
# -------------------------------------------------------
$newContent = Get-Content (Join-Path $modDir 'haven_extractor.py') -Raw
if ($newContent -match '__version__\s*=\s*"(\d+\.\d+\.\d+)"') {
    $newVersion = $Matches[1]
} else {
    $newVersion = $latestVersion
}

Write-Host ""
Write-Host "============================================================" -ForegroundColor Green
Write-Host "  Update complete! $currentVersion --> $newVersion" -ForegroundColor Green
Write-Host "============================================================" -ForegroundColor Green
Write-Host ""
Write-Host "  Previous mod files backed up to: mod_backup\"
Write-Host "  Your config and adjective cache have been preserved."
Write-Host ""
Write-Host "  Run RUN_HAVEN_EXTRACTOR.bat to start the extractor."
Write-Host ""
