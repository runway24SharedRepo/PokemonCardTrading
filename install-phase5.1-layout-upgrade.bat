@echo off
setlocal
cd /d "%~dp0"
chcp 65001 >nul
set PYTHONUTF8=1

echo ======================================================
echo Phase 5.1 - Link Layout and eBay Quota Checker
echo ======================================================
echo.
echo Close Pokemon-Auction-Scanner-Dashboard.xlsx first.
echo Existing Random Sniper and Live Radar algorithms are unchanged.
echo.

if not exist ".venv\Scripts\python.exe" (
    echo ERROR: Existing scanner Python environment was not found.
    goto :end
)

if not exist "Pokemon-Auction-Scanner-Dashboard.xlsx" (
    echo ERROR: Pokemon-Auction-Scanner-Dashboard.xlsx was not found.
    goto :end
)

".venv\Scripts\python.exe" upgrade_phase5_1_link_layout.py
set EXITCODE=%ERRORLEVEL%

echo.
echo Exit code: %EXITCODE%
if "%EXITCODE%"=="0" (
    echo SUCCESS.
    echo Continue using:
    echo   run-random-range-sniper.bat
    echo   run-live.bat
    echo.
    echo Check the daily eBay allowance with:
    echo   check-ebay-query-limits.bat
)

:end
echo.
pause
endlocal
