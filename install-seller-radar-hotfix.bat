@echo off
setlocal
cd /d "%~dp0"
chcp 65001 >nul
set PYTHONUTF8=1

echo ======================================================
echo Phase 5.3.1 - Seller Radar Configuration Hotfix
echo ======================================================
echo.
echo Fixes:
echo   location_country KeyError
echo   item_location_country compatibility
echo.

if not exist ".venv\Scripts\python.exe" (
    echo ERROR: Existing scanner Python environment was not found.
    goto :end
)

if not exist "seller_radar_client.py" (
    echo ERROR: seller_radar_client.py was not found.
    echo Copy this hotfix into the main scanner folder first.
    goto :end
)

".venv\Scripts\python.exe" -m py_compile seller_radar_client.py
set EXITCODE=%ERRORLEVEL%

echo.
echo Exit code: %EXITCODE%
if "%EXITCODE%"=="0" (
    echo HOTFIX INSTALLED.
    echo Close Excel and run sellerRadar.bat again.
)

:end
echo.
pause
endlocal
