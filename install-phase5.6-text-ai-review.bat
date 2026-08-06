@echo off
setlocal
cd /d "%~dp0"
chcp 65001 >nul
set PYTHONUTF8=1
set PYTHONUNBUFFERED=1

echo ======================================================
echo Phase 5.6 - Text-Only AI Listing Intelligence
echo ======================================================
echo.
echo Adds OpenAI review to Random, Snipe, Live and Seller modes.
echo Images remain disabled.
echo.
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

echo Installing OpenAI SDK...
".venv\Scripts\python.exe" -m pip install "openai>=2.31,<3" "pydantic>=2.8,<3"
if errorlevel 1 goto :end

".venv\Scripts\python.exe" -m py_compile ai_review_models.py ai_review_logic.py ai_review_cache.py ai_review_ebay.py ai_review_openai.py ai_review_excel.py run_ai_review.py upgrade_phase5_6_ai_review.py configure_openai_env.py check_openai_connection.py
if errorlevel 1 goto :end

".venv\Scripts\python.exe" -u upgrade_phase5_6_ai_review.py
set EXITCODE=%ERRORLEVEL%

echo.
echo Exit code: %EXITCODE%
if "%EXITCODE%"=="0" (
    echo PHASE 5.6 INSTALLED SUCCESSFULLY.
    echo.
    echo Next:
    echo   1. Run configureGPT.bat
    echo   2. Run testGPTConnection.bat
    echo   3. Run runGPTSmartReview.bat
)

:end
echo.
pause
endlocal
