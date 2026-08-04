@echo off
setlocal
cd /d "%~dp0"
chcp 65001 >nul
set PYTHONUTF8=1
set PYTHONUNBUFFERED=1

echo ======================================================
echo eBay Browse API - Remaining Query Allowance
echo ======================================================
echo.
echo This reads the production keyset from the existing .env file.
echo It does not run an eBay item search or modify Excel.
echo.

if not exist ".venv\Scripts\python.exe" (
    echo ERROR: Existing scanner Python environment was not found.
    goto :end
)

".venv\Scripts\python.exe" -u check_ebay_api_limits.py > ebay-api-limits.log 2>&1
set EXITCODE=%ERRORLEVEL%

type ebay-api-limits.log
echo.
echo Exit code: %EXITCODE%
echo Log: %CD%\ebay-api-limits.log

:end
echo.
pause
endlocal
