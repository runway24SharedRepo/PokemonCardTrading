@echo off
setlocal
cd /d "%~dp0"
chcp 65001 >nul
set PYTHONUTF8=1
set PYTHONUNBUFFERED=1

echo ======================================================
echo Phase 5.6.3.3 - Fast, Restart-Safe Live Radar
echo ======================================================
echo.
echo Progress is displayed and saved in live-radar.log.
echo Completed title matches and AI prices are checkpointed immediately.
echo Repeated listings reuse the persistent local caches.
echo The real workbook changes only after a fully successful run.
echo Invalid AI valuations are retried or marked pending without stopping the scan.
echo.
echo You may press Ctrl+C to stop safely. If the window is closed directly,
echo completed cache checkpoints still survive and the workbook stays safe.
echo.
echo Close Pokemon-Auction-Scanner-Dashboard.xlsx before continuing.
echo.

if not exist ".venv\Scripts\python.exe" (
    echo ERROR: Scanner Python environment was not found.
    echo Run the existing scanner installer first.
    goto :end
)

if not exist "Pokemon-Auction-Scanner-Dashboard.xlsx" (
    echo ERROR: Pokemon-Auction-Scanner-Dashboard.xlsx was not found.
    goto :end
)

".venv\Scripts\python.exe" -u live_opportunity_radar.py
set EXITCODE=%ERRORLEVEL%

echo.
echo Exit code: %EXITCODE%
if "%EXITCODE%"=="0" (
    echo SUCCESS: The completed workbook was committed safely.
) else if "%EXITCODE%"=="130" (
    echo INTERRUPTED SAFELY: Completed cache work was retained.
    echo The existing workbook was not changed.
) else (
    echo FAILED SAFELY: Review live-radar.log.
    echo The existing workbook was not replaced by a partial run.
)

:end
echo.
pause
endlocal
