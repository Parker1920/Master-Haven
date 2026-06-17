@echo off
cd /d C:\Master-Haven\SkyScraper
for /f "tokens=*" %%i in ('tailscale ip -4') do set TSIP=%%i
echo %TSIP% > _server_info.txt
echo.
echo ============================================
echo  SkyScraper Preview Server
echo  URL: http://%TSIP%:8090/
echo  Press Ctrl+C to stop
echo ============================================
echo.
python -m http.server 8090
