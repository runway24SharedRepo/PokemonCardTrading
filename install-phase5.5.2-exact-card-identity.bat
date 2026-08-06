@echo off
setlocal
cd /d "%~dp0"
chcp 65001 >nul
set PYTHONUTF8=1
set PYTHONUNBUFFERED=1

echo ======================================================
echo Phase 5.5.2 - Exact Pokemon Card Identity Matching
echo ======================================================
echo.
echo Fixes incorrect matches such as:
echo   Luxray 8 matching listing 028/88
echo   Mawile 9 matching listing 071/195
echo.
echo Applies to Random, Snipe, Live, Seller and same-seller modes.
echo No workbook structure change is required.
echo.

if not exist ".venv\Scripts\python.exe" (
    echo ERROR: Existing scanner Python environment was not found.
    goto :end
)

".venv\Scripts\python.exe" -m py_compile random_sniper\core.py random_sniper\seller_discovery.py live_radar\core.py random_range_sniper.py verify_card_identity_matching.py
if errorlevel 1 goto :end

".venv\Scripts\python.exe" -u verify_card_identity_matching.py
set EXITCODE=%ERRORLEVEL%

echo.
echo Exit code: %EXITCODE%
if "%EXITCODE%"=="0" (
    echo PHASE 5.5.2 INSTALLED SUCCESSFULLY.
    echo.
    echo Rerun the normal scanner to refresh active results:
    echo   run-random-range-sniper.bat
    echo   run-live.bat
    echo   sellerRadar.bat
) else (
    echo FAILED: Review the verification error above.
)

:end
echo.
pause
endlocal
