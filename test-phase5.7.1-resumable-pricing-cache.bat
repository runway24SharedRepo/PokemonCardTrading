@echo off
setlocal
cd /d "%~dp0"
set PYTHONUTF8=1

if exist ".venv\Scripts\python.exe" (
  ".venv\Scripts\python.exe" "tests\test_on_demand_pricing.py"
) else (
  py -3 "tests\test_on_demand_pricing.py"
)

exit /b %ERRORLEVEL%

