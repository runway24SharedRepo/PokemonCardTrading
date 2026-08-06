@echo off
setlocal
cd /d "%~dp0"
chcp 65001 >nul
set PYTHONUTF8=1
set PYTHONUNBUFFERED=1

echo ======================================================
echo Phase 5.5 - Long-Term Pokemon Investment Engine
echo ======================================================
echo.
echo Adds long-term scoring to Random, Snipe, Live and Seller modes.
echo Creates Portfolio Vault, Price History, Targets, Settings and Dashboard.
echo.
echo Close Pokemon-Auction-Scanner-Dashboard.xlsx before continuing.
echo.

if not exist ".venv\Scripts\python.exe" (
    echo ERROR: Existing scanner Python environment was not found.
    goto :end
)

if not exist "Pokemon-Auction-Scanner-Dashboard.xlsx" (
    echo ERROR: Pokemon-Auction-Scanner-Dashboard.xlsx was not found.
    goto :end
)

".venv\Scripts\python.exe" -m py_compile long_term_investment.py long_term_excel.py upgrade_phase5_5_long_term_investment.py random_range_sniper.py live_opportunity_radar.py seller_radar.py
if errorlevel 1 goto :end

".venv\Scripts\python.exe" -u upgrade_phase5_5_long_term_investment.py
set EXITCODE=%ERRORLEVEL%

echo.
echo Exit code: %EXITCODE%
if "%EXITCODE%"=="0" (
    echo PHASE 5.5 INSTALLED SUCCESSFULLY.
    echo.
    echo Continue using the normal launchers:
    echo   run-random-range-sniper.bat
    echo   run-live.bat
    echo   sellerRadar.bat
)

:end
echo.
pause
endlocal
