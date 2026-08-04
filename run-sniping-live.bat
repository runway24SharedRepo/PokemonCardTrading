@echo off
setlocal
cd /d "%~dp0"
echo Pokemon Auction Scanner - Live Sniping Scan
echo Close Pokemon-Auction-Scanner-Dashboard.xlsx before continuing.
echo.
".venv\Scripts\python.exe" sniping_scanner.py > sniping-live.log 2>&1
set EXITCODE=%ERRORLEVEL%
type sniping-live.log
echo.
echo Exit code: %EXITCODE%
if "%EXITCODE%"=="0" (
  echo SUCCESS: Open the workbook and inspect Snipe Queue.
) else (
  echo FAILED: Review sniping-live.log.
)
pause
endlocal
