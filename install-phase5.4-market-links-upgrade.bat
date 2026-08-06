@echo off
setlocal
cd /d "%~dp0"
chcp 65001 >nul
set PYTHONUTF8=1

 echo ======================================================
 echo Phase 5.4 - UK and Global Market Tracker Links
 echo ======================================================
 echo.
 echo Close Pokemon-Auction-Scanner-Dashboard.xlsx first.
 echo A timestamped workbook backup will be created.
 echo.

if not exist ".venv\Scripts\python.exe" (
    echo ERROR: Existing scanner Python environment was not found.
    goto :end
)

if not exist "Pokemon-Auction-Scanner-Dashboard.xlsx" (
    echo ERROR: Pokemon-Auction-Scanner-Dashboard.xlsx was not found.
    goto :end
)

".venv\Scripts\python.exe" -m py_compile market_links.py upgrade_phase5_4_market_links.py
if errorlevel 1 goto :end

".venv\Scripts\python.exe" upgrade_phase5_4_market_links.py
set EXITCODE=%ERRORLEVEL%

echo.
echo Exit code: %EXITCODE%
if "%EXITCODE%"=="0" (
    echo UPGRADE INSTALLED.
    echo Continue using the existing Random, Live and Seller BAT files.
)

:end
echo.
pause
endlocal
