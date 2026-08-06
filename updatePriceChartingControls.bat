@echo off
setlocal
cd /d "%~dp0"
chcp 65001 >nul
set PYTHONUTF8=1
set PYTHONUNBUFFERED=1

echo ======================================================
echo Update Market Controls from PriceCharting
echo ======================================================
echo.
echo Uses only rows where:
echo   Enabled = YES
echo   Auto Update = YES
echo.
echo Official PriceCharting API access is required.
echo Close Excel before continuing.
echo.

if not exist ".venv\Scripts\python.exe" (
    echo ERROR: Existing scanner Python environment was not found.
    goto :end
)

".venv\Scripts\python.exe" -u update_pricecharting_controls.py
set EXITCODE=%ERRORLEVEL%

echo.
echo Exit code: %EXITCODE%

:end
echo.
pause
endlocal
