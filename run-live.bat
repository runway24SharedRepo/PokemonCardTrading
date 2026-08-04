@echo off
setlocal
cd /d "%~dp0"
chcp 65001 >nul
set PYTHONUTF8=1
set PYTHONUNBUFFERED=1

echo ======================================================
echo Phase 5.2 - Live Opportunity Radar + eBay Watchlist
echo ======================================================
echo.
echo Broad UK Pokemon auction radar:
echo   - Ending inside the editable 2-minute to 24-hour window
echo   - Exact card matching against the full market database
echo   - Maximum-bid calculation
echo   - Detailed condition warning
echo   - GREEN seller expansion
echo   - GREEN listings added to My eBay Watchlist
echo.
echo Close Pokemon-Auction-Scanner-Dashboard.xlsx before continuing.
echo Live progress appears below and is also saved in:
echo live-radar.log
echo.

if not exist ".venv\Scripts\python.exe" (
    echo ERROR: Scanner Python environment was not found.
    echo Run install-live-radar-upgrade.bat first.
    goto :end
)

if not exist "Pokemon-Auction-Scanner-Dashboard.xlsx" (
    echo ERROR: Pokemon-Auction-Scanner-Dashboard.xlsx was not found.
    goto :end
)

".venv\Scripts\python.exe" -u live_opportunity_radar.py
set EXITCODE=%ERRORLEVEL%

echo.
echo Exit code: %EXITCODE%
if "%EXITCODE%"=="0" (
    echo SUCCESS: Open the workbook and review Live Opportunities.
) else if "%EXITCODE%"=="130" (
    echo INTERRUPTED: The hidden Excel process was released.
) else (
    echo FAILED: Review live-radar.log and Scanner Log.
)

:end
echo.
pause
endlocal
