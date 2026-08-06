@echo off
setlocal EnableExtensions
cd /d "%~dp0"
chcp 65001 >nul
set PYTHONUTF8=1
set PYTHONUNBUFFERED=1

echo ======================================================
echo Phase 5.5.3 - Edition-Safe Pokemon Pricing
echo ======================================================
echo.
echo Corrects Unlimited/Normal cards using First Edition values.
echo First Edition now requires explicit title evidence.
echo Generic edition-ambiguous images are no longer trusted.
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

".venv\Scripts\python.exe" -m py_compile edition_safety.py random_sniper\core.py random_sniper\excel_adapter.py live_radar\core.py live_radar\excel_adapter.py seller_radar_excel.py market_updater\pricing.py repair_existing_edition_prices.py verify_edition_safe_pricing.py
if errorlevel 1 goto :end

".venv\Scripts\python.exe" -u verify_edition_safe_pricing.py
if errorlevel 1 goto :end

echo.
echo Repairing edition-sensitive values already in the workbook...
".venv\Scripts\python.exe" -u repair_existing_edition_prices.py
set EXITCODE=%ERRORLEVEL%

echo.
echo Exit code: %EXITCODE%
if "%EXITCODE%"=="0" (
    echo PHASE 5.5.3 INSTALLED SUCCESSFULLY.
    echo.
    echo Rerun the scanner to rebuild active results:
    echo   run-random-range-sniper.bat
    echo   run-live.bat
    echo   sellerRadar.bat
) else (
    echo FAILED: Review the complete error above.
)

:end
echo.
pause
endlocal
