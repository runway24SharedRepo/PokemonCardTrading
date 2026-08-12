@echo off
setlocal EnableExtensions EnableDelayedExpansion
cd /d "%~dp0"
chcp 65001 >nul
set "PYTHONUTF8=1"
set "PYTHONUNBUFFERED=1"
set "PYTHONHOME="
set "PYTHONPATH="

echo ======================================================
echo Phase 5.7.4 - Transient API Retry Recovery
echo ======================================================
echo.
echo Close Pokemon-Auction-Scanner-Dashboard.xlsx and all scanner BAT files.
echo.

for /f %%I in ('powershell -NoProfile -Command "Get-Date -Format yyyyMMdd-HHmmss"') do set "STAMP=%%I"
if not defined STAMP set "STAMP=unknown-time"
if not exist "logs" mkdir "logs" >nul 2>&1
set "TESTLOG=logs\phase5.7.4-install-test-%STAMP%.log"

if not exist "Pokemon-Auction-Scanner-Dashboard.xlsx" (
  echo ERROR: Run this installer from the main PokemonCardTrading folder.
  echo The dashboard workbook was not found beside this BAT file.
  goto :failed
)

if not exist "payload\on_demand_pricing.py" (
  echo ERROR: The Phase 5.7.4 payload is missing or incomplete.
  goto :failed
)

if not exist "tests\test_on_demand_pricing.py" (
  echo ERROR: The Phase 5.7.4 regression test is missing.
  goto :failed
)

echo Running isolated pre-install tests...
if exist ".venv\Scripts\python.exe" (
  ".venv\Scripts\python.exe" -m py_compile payload\on_demand_pricing.py payload\clear_on_demand_price_failures.py payload\live_opportunity_radar.py payload\random_range_sniper.py payload\seller_radar.py payload\live_radar\excel_adapter.py payload\random_sniper\excel_adapter.py payload\random_sniper\core.py payload\long_term_excel.py payload\seller_radar_excel.py > "%TESTLOG%" 2>&1
  set "TEST_RC=!ERRORLEVEL!"
  if "!TEST_RC!"=="0" (
    ".venv\Scripts\python.exe" "tests\test_on_demand_pricing.py" >> "%TESTLOG%" 2>&1
    set "TEST_RC=!ERRORLEVEL!"
  )
) else (
  py -3 -m py_compile payload\on_demand_pricing.py payload\clear_on_demand_price_failures.py payload\live_opportunity_radar.py payload\random_range_sniper.py payload\seller_radar.py payload\live_radar\excel_adapter.py payload\random_sniper\excel_adapter.py payload\random_sniper\core.py payload\long_term_excel.py payload\seller_radar_excel.py > "%TESTLOG%" 2>&1
  set "TEST_RC=!ERRORLEVEL!"
  if "!TEST_RC!"=="0" (
    py -3 "tests\test_on_demand_pricing.py" >> "%TESTLOG%" 2>&1
    set "TEST_RC=!ERRORLEVEL!"
  )
)

type "%TESTLOG%"
echo.
if not "%TEST_RC%"=="0" (
  echo ERROR: The isolated pre-install tests failed with exit code %TEST_RC%.
  goto :failed
)

set "BACKUP=backups\phase5.7.4-source-before-%STAMP%"
mkdir "%BACKUP%\live_radar" >nul 2>&1
mkdir "%BACKUP%\random_sniper" >nul 2>&1
mkdir "%BACKUP%\market_updater" >nul 2>&1

for %%F in (on_demand_pricing.py live_opportunity_radar.py random_range_sniper.py seller_radar.py long_term_excel.py seller_radar_excel.py) do (
  if exist "%%F" copy /Y "%%F" "%BACKUP%\%%F" >nul
)
for %%F in (excel_adapter.py) do (
  if exist "live_radar\%%F" copy /Y "live_radar\%%F" "%BACKUP%\live_radar\%%F" >nul
  if exist "random_sniper\%%F" copy /Y "random_sniper\%%F" "%BACKUP%\random_sniper\%%F" >nul
)
if exist "random_sniper\core.py" copy /Y "random_sniper\core.py" "%BACKUP%\random_sniper\core.py" >nul
for %%F in (api.py pricing.py) do (
  if exist "market_updater\%%F" copy /Y "market_updater\%%F" "%BACKUP%\market_updater\%%F" >nul
)

call :copy_one "payload\on_demand_pricing.py" ".\on_demand_pricing.py"
if errorlevel 1 goto :failed
call :copy_one "payload\live_opportunity_radar.py" ".\live_opportunity_radar.py"
if errorlevel 1 goto :failed
call :copy_one "payload\random_range_sniper.py" ".\random_range_sniper.py"
if errorlevel 1 goto :failed
call :copy_one "payload\seller_radar.py" ".\seller_radar.py"
if errorlevel 1 goto :failed
call :copy_one "payload\long_term_excel.py" ".\long_term_excel.py"
if errorlevel 1 goto :failed
call :copy_one "payload\seller_radar_excel.py" ".\seller_radar_excel.py"
if errorlevel 1 goto :failed
call :copy_one "payload\live_radar\excel_adapter.py" ".\live_radar\excel_adapter.py"
if errorlevel 1 goto :failed
call :copy_one "payload\random_sniper\excel_adapter.py" ".\random_sniper\excel_adapter.py"
if errorlevel 1 goto :failed
call :copy_one "payload\random_sniper\core.py" ".\random_sniper\core.py"
if errorlevel 1 goto :failed
call :copy_one "payload\market_updater\api.py" ".\market_updater\api.py"
if errorlevel 1 goto :failed
call :copy_one "payload\market_updater\pricing.py" ".\market_updater\pricing.py"
if errorlevel 1 goto :failed

if exist ".venv\Scripts\python.exe" (
  ".venv\Scripts\python.exe" "payload\clear_on_demand_price_failures.py" "%CD%"
) else (
  py -3 "payload\clear_on_demand_price_failures.py" "%CD%"
)
if errorlevel 1 (
  echo ERROR: Could not clear the old Phase 5.7.3 failed-price checkpoints.
  goto :failed
)

echo INSTALLATION SUCCESSFUL
echo Source backup: %BACKUP%
echo Test log: %CD%\%TESTLOG%
echo.
echo Successful Cardmarket avg30 prices are shared for 24 hours.
echo Temporary API failures receive up to three controlled attempts.
echo Only final failures are warnings; recovered retries are reported separately.
goto :success

:copy_one
copy /Y "%~1" "%~2" >nul
if errorlevel 1 (
  echo ERROR: Could not copy %~1 to %~2.
  exit /b 1
)
exit /b 0

:failed
echo.
echo INSTALLATION FAILED.
if exist "%TESTLOG%" echo Full test log: %CD%\%TESTLOG%
echo The window will remain open so you can read or photograph this message.
echo.
pause
endlocal & exit /b 1

:success
echo.
pause
endlocal & exit /b 0
