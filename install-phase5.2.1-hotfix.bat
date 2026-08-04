@echo off
setlocal
cd /d "%~dp0"
chcp 65001 >nul
set PYTHONUTF8=1

echo ======================================================
echo Phase 5.2.1 - Watchlist Cleaner Hotfix
echo ======================================================
echo.
echo This hotfix makes cleanWatchlist.bat:
echo   - check the authorised account's Watchlist first
echo   - treat an empty Watchlist as success
echo   - fall back to removing actual ItemIDs when eBay returns 20820
echo.

if not exist ".venv\Scripts\python.exe" (
    echo ERROR: Existing scanner Python environment was not found.
    goto :end
)

".venv\Scripts\python.exe" -m py_compile ebay_watchlist.py manage_ebay_watchlist.py
set EXITCODE=%ERRORLEVEL%

echo.
echo Exit code: %EXITCODE%
if "%EXITCODE%"=="0" (
    echo HOTFIX INSTALLED.
    echo Run cleanWatchlist.bat again.
)

:end
echo.
pause
endlocal
