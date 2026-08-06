@echo off
setlocal
cd /d "%~dp0"
chcp 65001 >nul
set PYTHONUTF8=1

echo ======================================================
echo Configure Official PriceCharting API
echo ======================================================
echo.
echo PriceCharting API access requires a Legendary subscription.
echo The token is stored only in the local .env file.
echo.

if not exist ".venv\Scripts\python.exe" (
    echo ERROR: Existing scanner Python environment was not found.
    goto :end
)

".venv\Scripts\python.exe" configure_pricecharting_env.py

:end
echo.
pause
endlocal
