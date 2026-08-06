@echo off
setlocal
cd /d "%~dp0"
chcp 65001 >nul
set PYTHONUTF8=1
set PYTHONUNBUFFERED=1

echo ======================================================
echo Phase 5.6.1 - Market Value Authority Hotfix
echo ======================================================
echo.
echo Corrects inflated Normal-card values caused by Cardmarket
echo trend prices being selected ahead of TCGplayer market.
echo.
echo Market Data Import column H remains the single value used
echo by Random, Snipe, Live, Seller Radar, Long-Term and AI.
echo.
echo Close Pokemon-Auction-Scanner-Dashboard.xlsx first.
echo.

if not exist ".venv\Scripts\python.exe" (
    echo ERROR: Existing scanner Python environment was not found.
    goto :end
)

if not exist "Pokemon-Auction-Scanner-Dashboard.xlsx" (
    echo ERROR: Pokemon-Auction-Scanner-Dashboard.xlsx was not found.
    goto :end
)

".venv\Scripts\python.exe" -m py_compile market_price_controls.py market_updater\pricing.py market_updater\excel_writer.py repair_market_value_authority.py configure_pricecharting_env.py update_pricecharting_controls.py
if errorlevel 1 goto :end

".venv\Scripts\python.exe" -u repair_market_value_authority.py
set EXITCODE=%ERRORLEVEL%

echo.
echo Exit code: %EXITCODE%
if "%EXITCODE%"=="0" (
    echo PHASE 5.6.1 INSTALLED SUCCESSFULLY.
    echo.
    echo Existing Market Data Import values were recalculated.
    echo Future daily updates use TCGplayer market as primary.
    echo.
    echo Exact PriceCharting values:
    echo   - enter an override in Market Price Controls, or
    echo   - use configurePriceCharting.bat with an official API token.
    echo.
    echo Rerun your scanner to rebuild active opportunities.
)

:end
echo.
pause
endlocal
