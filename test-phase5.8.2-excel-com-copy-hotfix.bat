@echo off
setlocal EnableExtensions EnableDelayedExpansion
cd /d "%~dp0"
chcp 65001 >nul
set "PYTHONUTF8=1"
set "PYTHONHOME="
set "PYTHONPATH="

if exist ".venv\Scripts\python.exe" (
  ".venv\Scripts\python.exe" "tests\test_custom_live_scan.py"
  if errorlevel 1 goto :failed
  ".venv\Scripts\python.exe" "tests\test_no_scanner_watchlist_writes.py"
) else (
  py -3 "tests\test_custom_live_scan.py"
  if errorlevel 1 goto :failed
  py -3 "tests\test_no_scanner_watchlist_writes.py"
)
if errorlevel 1 goto :failed
echo.
echo ALL PHASE 5.8.2 TESTS PASSED.
echo.
pause
endlocal & exit /b 0

:failed
echo.
echo PHASE 5.8.2 TESTS FAILED.
echo.
pause
endlocal & exit /b 1
