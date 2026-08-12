@echo off
setlocal
cd /d "%~dp0"
set PYTHONUTF8=1

if exist ".venv\Scripts\python.exe" (
    ".venv\Scripts\python.exe" "tests\test_phase565_exact_tcgplayer.py"
) else (
    py -3 "tests\test_phase565_exact_tcgplayer.py"
)
set EXITCODE=%ERRORLEVEL%
echo.
echo Exit code: %EXITCODE%
pause
exit /b %EXITCODE%
