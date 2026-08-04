@echo off
setlocal
cd /d "%~dp0"
chcp 65001 >nul
set PYTHONUTF8=1

echo ======================================================
echo Phase 5 Live Opportunity Radar - One-Time Upgrade
echo ======================================================
echo.
echo Close Pokemon-Auction-Scanner-Dashboard.xlsx first.
echo The Random Range Sniper will not be changed.
echo.

if not exist ".venv\Scripts\python.exe" (
    echo Existing .venv was not found. Creating it now...
    py -m venv .venv
    if errorlevel 1 python -m venv .venv
)

if not exist ".venv\Scripts\python.exe" (
    echo ERROR: Python environment could not be created.
    goto :end
)

".venv\Scripts\python.exe" -m pip install -r requirements-live-radar.txt
if errorlevel 1 goto :end

".venv\Scripts\python.exe" setup_live_opportunity_radar.py
set EXITCODE=%ERRORLEVEL%

echo.
echo Exit code: %EXITCODE%
if "%EXITCODE%"=="0" (
    echo SUCCESS: Continue using the replaced run-live.bat.
)

:end
echo.
pause
endlocal
