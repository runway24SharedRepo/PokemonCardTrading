@echo off
setlocal
cd /d "%~dp0"
chcp 65001 >nul
set PYTHONUTF8=1

echo ======================================================
echo Random Range Sniper - Reroll Cards Only
echo ======================================================
echo.
echo Close Pokemon-Auction-Scanner-Dashboard.xlsx before continuing.
echo This selects new cards but does not contact eBay.
echo.

if not exist ".venv\Scripts\python.exe" (
    echo ERROR: Run install-random-range-sniper.bat first.
    goto :end
)

".venv\Scripts\python.exe" random_range_sniper.py --reroll-only
set EXITCODE=%ERRORLEVEL%

echo.
echo Exit code: %EXITCODE%
if "%EXITCODE%"=="0" (
    echo SUCCESS: Open the Random Range Sniper tab.
)

:end
echo.
pause
endlocal
