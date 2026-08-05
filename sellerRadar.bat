@echo off
setlocal EnableExtensions
cd /d "%~dp0"
chcp 65001 >nul
set PYTHONUTF8=1
set PYTHONUNBUFFERED=1

echo ======================================================
echo Phase 5.3 - eBay Seller Radar
echo ======================================================
echo.
echo Creates or refreshes one dedicated worksheet for an eBay seller.
echo Analyses auctions and Buy It Now Pokemon-card listings.
echo.
echo Close Pokemon-Auction-Scanner-Dashboard.xlsx before continuing.
echo Live progress appears below and is saved in:
echo seller-radar.log
echo.

if not exist ".venv\Scripts\python.exe" (
    echo ERROR: Existing scanner Python environment was not found.
    echo Run install-seller-radar-addon.bat first.
    goto :end
)

if not exist "Pokemon-Auction-Scanner-Dashboard.xlsx" (
    echo ERROR: Pokemon-Auction-Scanner-Dashboard.xlsx was not found.
    goto :end
)

set "SELLER="
set /p "SELLER=Enter the exact eBay seller username: "
if not defined SELLER (
    echo ERROR: A seller username is required.
    goto :end
)

set "SCANCOUNT="
set /p "SCANCOUNT=Maximum active listings to scan [50]: "
if not defined SCANCOUNT set "SCANCOUNT=50"

echo.
echo Seller: %SELLER%
echo Listing cap: %SCANCOUNT%
echo.

".venv\Scripts\python.exe" -u seller_radar.py --seller "%SELLER%" --limit "%SCANCOUNT%"
set EXITCODE=%ERRORLEVEL%

echo.
echo Exit code: %EXITCODE%
if "%EXITCODE%"=="0" (
    echo SUCCESS: Open the workbook and review the new Seller worksheet.
) else if "%EXITCODE%"=="130" (
    echo INTERRUPTED: The hidden Excel process was released.
) else (
    echo FAILED: Review seller-radar.log.
)

:end
echo.
pause
endlocal
