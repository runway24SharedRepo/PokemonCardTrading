@echo off
setlocal
cd /d "%~dp0"
chcp 65001 >nul
set PYTHONUTF8=1
set PYTHONUNBUFFERED=1

echo ======================================================
echo Apply Market Price Controls
echo ======================================================
echo.
echo Recalculates Market Data Import column H.
echo TCGplayer market is primary.
echo Cardmarket is fallback only.
echo Verified overrides take priority.
echo.
echo Close Excel before continuing.
echo.

if not exist ".venv\Scripts\python.exe" (
    echo ERROR: Existing scanner Python environment was not found.
    goto :end
)

".venv\Scripts\python.exe" -u repair_market_value_authority.py
set EXITCODE=%ERRORLEVEL%

echo.
echo Exit code: %EXITCODE%

:end
echo.
pause
endlocal
