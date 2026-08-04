@echo off
setlocal
cd /d "%~dp0"
chcp 65001 >nul
set PYTHONUTF8=1

echo ======================================================
echo Phase 5.2 - eBay Watchlist Integration
echo ======================================================
echo.
echo This is a code-only upgrade.
echo It does not change the spreadsheet layout or market database.
echo.

if not exist ".venv\Scripts\python.exe" (
    echo ERROR: Existing scanner Python environment was not found.
    goto :end
)

".venv\Scripts\python.exe" -m pip install "requests>=2.32,<3" "python-dotenv>=1.0,<2"
if errorlevel 1 goto :end

".venv\Scripts\python.exe" configure_ebay_watchlist_env.py
set EXITCODE=%ERRORLEVEL%

echo.
echo Exit code: %EXITCODE%
if "%EXITCODE%"=="0" (
    echo UPGRADE INSTALLED.
    echo.
    echo Next step:
    echo   Run configure-ebay-watchlist-auth.bat
    echo.
    echo Existing daily launchers remain:
    echo   run-random-range-sniper.bat
    echo   run-live.bat
    echo.
    echo Watchlist cleanup:
    echo   cleanWatchlist.bat
)

:end
echo.
pause
endlocal
