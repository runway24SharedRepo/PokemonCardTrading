@echo off
setlocal
cd /d "%~dp0"
chcp 65001 >nul
set PYTHONUTF8=1

echo ======================================================
echo Phase 5.3 Seller Radar - One-Time Installation
echo ======================================================
echo.
echo This is a code-only add-on.
echo It does not change Random Sniper or Live Radar sheets.
echo.

if not exist ".venv\Scripts\python.exe" (
    echo ERROR: Existing scanner Python environment was not found.
    goto :end
)

".venv\Scripts\python.exe" -m pip install "requests>=2.32,<3" "python-dotenv>=1.0,<2"
if errorlevel 1 goto :end

".venv\Scripts\python.exe" -m py_compile seller_radar.py seller_radar_client.py seller_radar_excel.py
set EXITCODE=%ERRORLEVEL%

echo.
echo Exit code: %EXITCODE%
if "%EXITCODE%"=="0" (
    echo SELLER RADAR INSTALLED.
    echo.
    echo Run:
    echo   sellerRadar.bat
)

:end
echo.
pause
endlocal
