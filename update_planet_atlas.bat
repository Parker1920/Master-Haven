@echo off
echo ==========================================
echo   Planet_Atlas Submodule Update Script
echo ==========================================
echo.

cd /d "%~dp0"

echo Checking for Planet_Atlas submodule...
if not exist "Planet_Atlas\.git" (
    echo ERROR: Planet_Atlas submodule not found!
    echo Run: git submodule update --init --recursive
    pause
    exit /b 1
)

echo.
echo Fetching latest changes from upstream...
cd Planet_Atlas
git fetch origin

echo.
echo Checking out main branch...
git checkout main

echo.
echo Pulling latest updates...
git pull origin main

cd ..

echo.
echo ==========================================
echo   Planet_Atlas updated successfully!
echo ==========================================
echo.
echo Don't forget to restart the Haven server
echo to apply any changes.
echo.
pause
