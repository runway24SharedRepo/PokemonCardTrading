@echo off
setlocal
cd /d "%~dp0"
chcp 65001 >nul
set PYTHONUTF8=1

echo ======================================================
echo Phase 5.3.2 - Seller Radar Progress Memory Upgrade
echo ======================================================
echo.
echo Adds persistent next-unscanned batching for every seller.
echo No existing seller history is required; the first run starts normally.
echo.

if not exist ".venv\Scripts\python.exe" (
    echo ERROR: Existing scanner Python environment was not found.
    goto :end
)

".venv\Scripts\python.exe" -m py_compile seller_radar.py seller_radar_client.py seller_radar_excel.py seller_radar_history.py manage_seller_radar_history.py
set EXITCODE=%ERRORLEVEL%

echo.
echo Exit code: %EXITCODE%
if "%EXITCODE%"=="0" (
    echo UPGRADE INSTALLED.
    echo.
    echo Continue with:
    echo   sellerRadar.bat
    echo.
    echo Optional history reset:
    echo   resetSellerRadarHistory.bat
)

:end
echo.
pause
endlocal
