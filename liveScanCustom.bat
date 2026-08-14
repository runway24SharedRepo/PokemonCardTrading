@echo off
setlocal EnableExtensions
cd /d "%~dp0"
chcp 65001 >nul
set "PYTHONUTF8=1"
set "PYTHONUNBUFFERED=1"
set "PYTHONHOME="
set "PYTHONPATH="
title Pokemon Custom Live Scan

echo ==============================================================
echo Pokemon Custom Live Scan - Manual Market Data Import Column H
echo ==============================================================
echo.
echo Close Pokemon-Auction-Scanner-Dashboard.xlsx before continuing.
echo Selected cards: pokemonInput.txt
echo Reference cost: Market Data Import column H
echo Results: Custom Live Results and Custom Live Queue
echo eBay Watchlist writes: DISABLED
echo.

if not exist "Pokemon-Auction-Scanner-Dashboard.xlsx" (
  echo ERROR: Pokemon-Auction-Scanner-Dashboard.xlsx was not found.
  goto :failed
)
if not exist "pokemonInput.txt" (
  echo ERROR: pokemonInput.txt was not found.
  goto :failed
)
if not exist "live_scan_custom.py" (
  echo ERROR: live_scan_custom.py was not found.
  goto :failed
)

if exist ".venv\Scripts\python.exe" (
  ".venv\Scripts\python.exe" "live_scan_custom.py" --input "pokemonInput.txt" %*
) else (
  py -3 "live_scan_custom.py" --input "pokemonInput.txt" %*
)
set "SCAN_RC=%ERRORLEVEL%"
if not "%SCAN_RC%"=="0" goto :failed_code

echo.
echo Scan completed successfully.
echo Open Custom Live Results or Custom Live Queue in the workbook.
echo Full log: %CD%\custom-live-scan.log
echo.
pause
endlocal & exit /b 0

:failed
set "SCAN_RC=1"
:failed_code
echo.
echo CUSTOM LIVE SCAN FAILED with exit code %SCAN_RC%.
echo The existing workbook was not replaced by a partial run.
if exist "custom-live-scan.log" echo Full log: %CD%\custom-live-scan.log
echo.
pause
endlocal & exit /b %SCAN_RC%
