@echo off
setlocal
cd /d "%~dp0"
chcp 65001 >nul
set PYTHONUTF8=1

echo ======================================================
echo Phase 4.2 Random Range Sniper - Upgrade
echo ======================================================
echo.
echo Close Pokemon-Auction-Scanner-Dashboard.xlsx first.
echo A timestamped workbook backup will be created.
echo.

if not exist ".venv\Scripts\python.exe" (
    echo ERROR: Existing scanner Python environment not found.
    goto :end
)

if not exist "Pokemon-Auction-Scanner-Dashboard.xlsx" (
    echo ERROR: Pokemon-Auction-Scanner-Dashboard.xlsx was not found.
    goto :end
)

".venv\Scripts\python.exe" upgrade_random_range_sniper_4_2.py
set EXITCODE=%ERRORLEVEL%

echo.
echo Exit code: %EXITCODE%
if "%EXITCODE%"=="0" (
    echo SUCCESS: Run run-random-range-sniper.bat again.
)

:end
echo.
pause
endlocal
