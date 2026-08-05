@echo off
setlocal EnableExtensions
cd /d "%~dp0"
chcp 65001 >nul
set PYTHONUTF8=1
set PYTHONUNBUFFERED=1

echo ======================================================
echo Seller Radar - Select and Reset Tracked Sellers
echo ======================================================
echo.
echo Displays every seller currently tracked by Seller Radar.
echo You can remove one or several histories using numbers such as:
echo.
echo   3;4
echo   1,3
echo   2-4
echo   A
echo.
echo This resets scan progress only.
echo Existing Seller worksheets in Excel are preserved.
echo.

if not exist ".venv\Scripts\python.exe" (
    echo ERROR: Existing scanner Python environment was not found.
    goto :end
)

".venv\Scripts\python.exe" -u manage_seller_radar_history.py --interactive-reset
set EXITCODE=%ERRORLEVEL%

echo.
echo Exit code: %EXITCODE%

:end
echo.
pause
endlocal
