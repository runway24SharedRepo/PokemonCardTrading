@echo off
setlocal
cd /d "%~dp0"

echo ======================================================
echo Pokemon Market API and FX Connection Test
echo ======================================================
echo.

if not exist ".venv\Scripts\python.exe" (
    echo ERROR: Run install-market-updater.bat first.
    goto :end
)

".venv\Scripts\python.exe" update_pokemon_market.py --test > market-connection-test.log 2>&1
set EXITCODE=%ERRORLEVEL%

type market-connection-test.log
echo.
echo Exit code: %EXITCODE%
echo Log: %CD%\market-connection-test.log

:end
echo.
pause
endlocal
