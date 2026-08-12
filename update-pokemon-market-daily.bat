@echo off
setlocal
cd /d "%~dp0"
chcp 65001 >nul
set PYTHONUTF8=1

echo ======================================================
echo Pokemon Full Card Database - Daily Market Update
echo ======================================================
echo.
echo IMPORTANT:
echo Close Pokemon-Auction-Scanner-Dashboard.xlsx before continuing.
echo.
echo This update downloads the full English card catalogue,
echo refreshes GBP average selling prices, updates Excel and saves history.
echo.
echo Interrupted downloads now resume automatically.
echo.

if not exist ".venv\Scripts\python.exe" (
    echo ERROR: Run install-market-updater.bat first.
    goto :end
)

if not exist "Pokemon-Auction-Scanner-Dashboard.xlsx" (
    echo ERROR: Pokemon-Auction-Scanner-Dashboard.xlsx was not found.
    echo Place these updater files inside the scanner folder.
    goto :end
)

echo Starting updater. Progress is shown live and saved to:
echo   pokemon-market-daily.log
echo.
powershell -NoProfile -ExecutionPolicy Bypass -Command ^
  "& '.\.venv\Scripts\python.exe' '.\update_pokemon_market.py' 2>&1 | Tee-Object -FilePath '.\pokemon-market-daily.log'; exit $LASTEXITCODE"
set EXITCODE=%ERRORLEVEL%
echo.
echo Exit code: %EXITCODE%

if "%EXITCODE%"=="0" (
    echo SUCCESS: Open the workbook and review:
    echo   - Market Update Summary
    echo   - Market Data Import
    echo   - Full Card Database
    echo   - Market Price Changes
    echo   - Price Import Log
) else (
    echo FAILED: Review pokemon-market-daily.log.
    echo Downloaded pages were preserved.
    echo Run this BAT again later to resume automatically.
)

:end
echo.
pause
endlocal
