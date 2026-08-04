@echo off
setlocal
cd /d "%~dp0"
chcp 65001 >nul
set PYTHONUTF8=1
set PYTHONUNBUFFERED=1

echo ======================================================
echo eBay Watchlist Cleaner
echo ======================================================
echo.
echo Safe default:
echo   Remove only listings added by the Pokemon scanner.
echo.
echo Optional destructive mode:
echo   Remove EVERY item from your eBay Watchlist.
echo   This requires typing DELETE ALL.
echo.

if not exist ".venv\Scripts\python.exe" (
    echo ERROR: Existing scanner Python environment was not found.
    goto :end
)

".venv\Scripts\python.exe" -u manage_ebay_watchlist.py
set EXITCODE=%ERRORLEVEL%

echo.
echo Exit code: %EXITCODE%

:end
echo.
pause
endlocal
