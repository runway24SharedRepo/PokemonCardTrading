@echo off
setlocal
cd /d "%~dp0"
chcp 65001 >nul
set PYTHONUTF8=1

echo ======================================================
echo Phase 4 Random Range Sniper - Installation
echo ======================================================
echo.
echo Close Pokemon-Auction-Scanner-Dashboard.xlsx first.
echo.

if not exist ".venv\Scripts\python.exe" (
    echo Existing scanner .venv was not found.
    echo Creating it now...
    py -m venv .venv
    if errorlevel 1 python -m venv .venv
)

if not exist ".venv\Scripts\python.exe" (
    echo ERROR: Python environment could not be created.
    goto :end
)

".venv\Scripts\python.exe" -m pip install -r requirements-random-sniper.txt
if errorlevel 1 goto :end

if not exist "Pokemon-Auction-Scanner-Dashboard.xlsx" (
    echo ERROR: Pokemon-Auction-Scanner-Dashboard.xlsx was not found.
    echo Copy these files into the existing scanner folder.
    goto :end
)

".venv\Scripts\python.exe" setup_random_range_sniper.py
set EXITCODE=%ERRORLEVEL%

if "%EXITCODE%"=="0" (
    echo.
    echo Installation successful.
    echo Next run test-random-range-sniper-api.bat.
)

:end
echo.
pause
endlocal
