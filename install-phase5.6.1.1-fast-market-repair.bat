@echo off
setlocal EnableExtensions
cd /d "%~dp0"
chcp 65001 >nul
set PYTHONUTF8=1
set PYTHONIOENCODING=utf-8
set PYTHONUNBUFFERED=1
set PYTHONFAULTHANDLER=1

echo ======================================================
echo Phase 5.6.1.1 - Fast Market Repair Hotfix
echo ======================================================
echo.
echo Replaces the slow cell-by-cell Phase 5.6.1 repair.
echo Shows progress and writes Market Data Import in one operation.
echo.
echo Close Pokemon-Auction-Scanner-Dashboard.xlsx first.
echo.

if not exist ".venv\Scripts\python.exe" (
    echo ERROR: Existing scanner Python environment was not found.
    goto :end
)

if not exist "Pokemon-Auction-Scanner-Dashboard.xlsx" (
    echo ERROR: Pokemon-Auction-Scanner-Dashboard.xlsx was not found.
    goto :end
)

echo [Installer 1/2] Checking Python files...
".venv\Scripts\python.exe" -m py_compile market_price_controls.py repair_market_value_authority.py
if errorlevel 1 goto :end

echo.
echo [Installer 2/2] Starting fast bulk workbook repair...
echo.
".venv\Scripts\python.exe" -u repair_market_value_authority.py
set EXITCODE=%ERRORLEVEL%

echo.
echo Exit code: %EXITCODE%
if "%EXITCODE%"=="0" (
    echo PHASE 5.6.1.1 INSTALLED SUCCESSFULLY.
    echo.
    echo Rerun Random, Live and Seller Radar to rebuild active results.
) else (
    echo FAILED: Review the complete error above.
)

:end
echo.
pause
endlocal
