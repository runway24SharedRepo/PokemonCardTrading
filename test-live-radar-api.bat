@echo off
setlocal
cd /d "%~dp0"
chcp 65001 >nul
set PYTHONUTF8=1
set PYTHONUNBUFFERED=1

echo ======================================================
echo Live Opportunity Radar - eBay API Test
echo ======================================================
echo.

if not exist ".venv\Scripts\python.exe" (
    echo ERROR: Run install-live-radar-upgrade.bat first.
    goto :end
)

".venv\Scripts\python.exe" -u live_opportunity_radar.py --test-api
set EXITCODE=%ERRORLEVEL%

echo.
echo Exit code: %EXITCODE%

:end
echo.
pause
endlocal
