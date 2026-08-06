@echo off
setlocal
cd /d "%~dp0"
chcp 65001 >nul
set PYTHONUTF8=1

echo ======================================================
echo Phase 5.4.1 - Smart Market-Link Search Upgrade
echo ======================================================
echo.
echo New tracker query format:
echo   clean card name + collector number/ID
echo.
echo Example:
echo   Kyogre-EX + XY Black Star Promos + XY41
echo   becomes Kyogre EX XY41
echo.
echo Close Pokemon-Auction-Scanner-Dashboard.xlsx before continuing.
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
    echo SMART MARKET LINKS INSTALLED.
    echo Existing workbook links were refreshed.
    echo Future Random, Live and Seller scans use the new query automatically.
)

:end
echo.
pause
endlocal
