@echo off
setlocal
cd /d "%~dp0"
chcp 65001 >nul
set PYTHONUTF8=1

echo ======================================================
echo Configure eBay Personal Watchlist Access
echo ======================================================
echo.

if not exist ".venv\Scripts\python.exe" (
    echo ERROR: Existing scanner Python environment was not found.
    goto :end
)

".venv\Scripts\python.exe" configure_ebay_watchlist_env.py
set EXITCODE=%ERRORLEVEL%

if not "%EXITCODE%"=="0" goto :end

echo.
echo Opening .env in Notepad...
echo Add ONE valid production user token, save, and close Notepad.
echo.
start "" /wait notepad.exe ".env"

echo.
echo Testing the authorised Watchlist connection...
".venv\Scripts\python.exe" -u manage_ebay_watchlist.py --status
set EXITCODE=%ERRORLEVEL%

:end
echo.
echo Exit code: %EXITCODE%
echo.
pause
endlocal
