@echo off
setlocal
cd /d "%~dp0"
chcp 65001 >nul
set PYTHONUTF8=1

echo ======================================================
echo Phase 5.4.2 - Seller History Numbered Selector
echo ======================================================
echo.
echo Upgrades resetSellerRadarHistory.bat with:
echo   - tracked seller list
echo   - numbered selection
echo   - multi-seller reset
echo   - one shared backup
echo.

if not exist ".venv\Scripts\python.exe" (
    echo ERROR: Existing scanner Python environment was not found.
    goto :end
)

".venv\Scripts\python.exe" -m py_compile seller_radar_history.py manage_seller_radar_history.py
set EXITCODE=%ERRORLEVEL%

echo.
echo Exit code: %EXITCODE%
if "%EXITCODE%"=="0" (
    echo UPGRADE INSTALLED.
    echo.
    echo Run:
    echo   resetSellerRadarHistory.bat
)

:end
echo.
pause
endlocal
