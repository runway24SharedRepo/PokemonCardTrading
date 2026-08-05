@echo off
setlocal EnableExtensions
cd /d "%~dp0"
chcp 65001 >nul
set PYTHONUTF8=1
set PYTHONUNBUFFERED=1

echo ======================================================
echo Seller Radar - Reset One Seller's Scan History
echo ======================================================
echo.
echo This does not delete the seller worksheet.
echo It makes the next scan begin again from the first currently active
echo listing for the selected seller.
echo.

if not exist ".venv\Scripts\python.exe" (
    echo ERROR: Existing scanner Python environment was not found.
    goto :end
)

set "SELLER="
set /p "SELLER=Enter the exact eBay seller username: "
if not defined SELLER (
    echo ERROR: A seller username is required.
    goto :end
)

".venv\Scripts\python.exe" -u manage_seller_radar_history.py --seller "%SELLER%" --reset
set EXITCODE=%ERRORLEVEL%

echo.
echo Exit code: %EXITCODE%

:end
echo.
pause
endlocal
