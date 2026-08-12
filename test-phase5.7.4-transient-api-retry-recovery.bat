@echo off
setlocal EnableExtensions
cd /d "%~dp0"
chcp 65001 >nul
set "PYTHONUTF8=1"
set "PYTHONUNBUFFERED=1"
set "PYTHONHOME="
set "PYTHONPATH="

for /f %%I in ('powershell -NoProfile -Command "Get-Date -Format yyyyMMdd-HHmmss"') do set "STAMP=%%I"
if not defined STAMP set "STAMP=unknown-time"
if not exist "logs" mkdir "logs" >nul 2>&1
set "TESTLOG=logs\phase5.7.4-manual-test-%STAMP%.log"

if exist ".venv\Scripts\python.exe" (
  ".venv\Scripts\python.exe" "tests\test_on_demand_pricing.py" > "%TESTLOG%" 2>&1
) else (
  py -3 "tests\test_on_demand_pricing.py" > "%TESTLOG%" 2>&1
)
set "TEST_RC=%ERRORLEVEL%"
type "%TESTLOG%"
echo.
echo Full test log: %CD%\%TESTLOG%
if not "%TEST_RC%"=="0" (
  echo TEST FAILED with exit code %TEST_RC%.
) else (
  echo TEST PASSED.
)
echo.
pause
endlocal & exit /b %TEST_RC%
