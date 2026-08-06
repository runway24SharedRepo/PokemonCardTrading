@echo off
setlocal
cd /d "%~dp0"
chcp 65001 >nul
set PYTHONUTF8=1
set PYTHONUNBUFFERED=1

echo ======================================================
echo Phase 5.5.1 - Long-Term Dashboard Merged-Cell Hotfix
echo ======================================================
echo.
echo Fixes:
echo   We can't do that to a merged cell.
echo.
echo The interrupted Phase 5.5 installation is safe to rerun.
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

".venv\Scripts\python.exe" -m py_compile long_term_excel.py upgrade_phase5_5_long_term_investment.py
if errorlevel 1 goto :end

".venv\Scripts\python.exe" -u upgrade_phase5_5_long_term_investment.py
set EXITCODE=%ERRORLEVEL%

echo.
echo Exit code: %EXITCODE%
if "%EXITCODE%"=="0" (
    echo PHASE 5.5.1 HOTFIX INSTALLED SUCCESSFULLY.
    echo The partially installed Phase 5.5 workbook was completed.
) else (
    echo FAILED: Review the complete error above.
)

:end
echo.
pause
endlocal
