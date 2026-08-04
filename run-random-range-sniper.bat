@echo off
setlocal
cd /d "%~dp0"
chcp 65001 >nul
set PYTHONUTF8=1

echo ======================================================
echo Phase 4 - Random Range Sniper
echo ======================================================
echo.
echo Close Pokemon-Auction-Scanner-Dashboard.xlsx before continuing.
echo The live progress is displayed below and saved in:
echo random-range-sniper.log
echo.

if not exist ".venv\Scripts\python.exe" (
    echo ERROR: Run install-random-range-sniper.bat first.
    goto :end
)

".venv\Scripts\python.exe" random_range_sniper.py
set EXITCODE=%ERRORLEVEL%

echo.
echo Exit code: %EXITCODE%
if "%EXITCODE%"=="0" (
    echo SUCCESS: Open the workbook and review:
    echo   - Random Range Sniper
    echo   - Random Snipe Results
    echo   - Random Snipe Queue
    echo   - Random Snipe History
    echo   - Snipe Queue
) else (
    echo FAILED: Review random-range-sniper.log.
)

:end
echo.
pause
endlocal
