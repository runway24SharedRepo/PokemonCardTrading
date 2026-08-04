@echo off
setlocal
cd /d "%~dp0"
chcp 65001 >nul
set PYTHONUTF8=1

echo ======================================================
echo Random Range Sniper - eBay API Test
echo ======================================================
echo.

if not exist ".venv\Scripts\python.exe" (
    echo ERROR: Run install-random-range-sniper.bat first.
    goto :end
)

".venv\Scripts\python.exe" random_range_sniper.py --test-api
set EXITCODE=%ERRORLEVEL%

echo.
echo Exit code: %EXITCODE%

:end
echo.
pause
endlocal
