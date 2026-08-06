@echo off
setlocal
cd /d "%~dp0"
chcp 65001 >nul
set PYTHONUTF8=1
set PYTHONUNBUFFERED=1

echo ======================================================
echo Phase 5.6.4 - Free TCG Market Pricing - No AI
echo ======================================================
echo.
echo Restores the original free Pokemon TCG market-price method.
echo Removes OpenAI from every automatic scanner path.
echo Preserves eBay credentials, Pokemon TCG credentials and title cache.
echo.
echo Close Pokemon-Auction-Scanner-Dashboard.xlsx first.
echo.

if not exist ".venv\Scripts\python.exe" (
    echo ERROR: Existing scanner Python environment was not found.
    goto :end
)

".venv\Scripts\python.exe" -m py_compile disable_ai_integration.py live_opportunity_radar.py random_range_sniper.py seller_radar.py update_pokemon_market.py market_price_controls.py listing_identification_cache.py market_updater\pricing.py market_updater\excel_writer.py test_phase564_offline.py
if errorlevel 1 (
    echo ERROR: Python validation failed.
    goto :end
)

".venv\Scripts\python.exe" test_phase564_offline.py
if errorlevel 1 (
    echo ERROR: Offline rollback tests failed.
    goto :end
)

".venv\Scripts\python.exe" disable_ai_integration.py
set EXITCODE=%ERRORLEVEL%

echo.
echo Exit code: %EXITCODE%
if "%EXITCODE%"=="0" (
    echo PHASE 5.6.4 INSTALLED SUCCESSFULLY.
    echo.
    echo Pricing source:
    echo   Pokemon TCG API / TCGplayer market
    echo   Cardmarket only when the exact TCGplayer variant has no price
    echo.
    echo OpenAI API calls from this project: DISABLED
    echo.
    echo Next:
    echo   1. Run update-pokemon-market-daily.bat
    echo   2. Run run-live.bat or run-random-range-sniper.bat
)

:end
echo.
pause
endlocal
