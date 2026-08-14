@echo off
setlocal EnableExtensions EnableDelayedExpansion
cd /d "%~dp0"
chcp 65001 >nul
set "PYTHONUTF8=1"
set "PYTHONUNBUFFERED=1"
set "PYTHONHOME="
set "PYTHONPATH="

echo ==============================================================
echo Phase 5.8 - Custom Live Scan
echo ==============================================================
echo.
echo Close Pokemon-Auction-Scanner-Dashboard.xlsx and every scanner BAT.
echo.

for /f %%I in ('powershell -NoProfile -Command "Get-Date -Format yyyyMMdd-HHmmss"') do set "STAMP=%%I"
if not defined STAMP set "STAMP=unknown-time"
if not exist "logs" mkdir "logs" >nul 2>&1
set "TESTLOG=logs\phase5.8-install-test-%STAMP%.log"

if not exist "Pokemon-Auction-Scanner-Dashboard.xlsx" (
  echo ERROR: Run this installer from the main PokemonCardTrading folder.
  goto :failed
)
if not exist "random-sniper-config.json" (
  echo ERROR: random-sniper-config.json was not found.
  goto :failed
)
if not exist "random_sniper\ebay_client.py" (
  echo ERROR: The existing Random Range Sniper installation is incomplete.
  goto :failed
)
if not exist "payload\live_scan_custom.py" (
  echo ERROR: The Phase 5.8 payload is incomplete.
  goto :failed
)

echo Running isolated pre-install tests...
if exist ".venv\Scripts\python.exe" (
  ".venv\Scripts\python.exe" -m py_compile payload\custom_input.py payload\live_scan_custom.py payload\random_range_sniper.py payload\live_opportunity_radar.py payload\random_sniper\excel_adapter.py > "%TESTLOG%" 2>&1
  set "TEST_RC=!ERRORLEVEL!"
  if "!TEST_RC!"=="0" (
    ".venv\Scripts\python.exe" "tests\test_custom_live_scan.py" >> "%TESTLOG%" 2>&1
    set "TEST_RC=!ERRORLEVEL!"
  )
  if "!TEST_RC!"=="0" (
    ".venv\Scripts\python.exe" "tests\test_no_scanner_watchlist_writes.py" >> "%TESTLOG%" 2>&1
    set "TEST_RC=!ERRORLEVEL!"
  )
) else (
  py -3 -m py_compile payload\custom_input.py payload\live_scan_custom.py payload\random_range_sniper.py payload\live_opportunity_radar.py payload\random_sniper\excel_adapter.py > "%TESTLOG%" 2>&1
  set "TEST_RC=!ERRORLEVEL!"
  if "!TEST_RC!"=="0" (
    py -3 "tests\test_custom_live_scan.py" >> "%TESTLOG%" 2>&1
    set "TEST_RC=!ERRORLEVEL!"
  )
  if "!TEST_RC!"=="0" (
    py -3 "tests\test_no_scanner_watchlist_writes.py" >> "%TESTLOG%" 2>&1
    set "TEST_RC=!ERRORLEVEL!"
  )
)

type "%TESTLOG%"
echo.
if not "%TEST_RC%"=="0" (
  echo ERROR: Phase 5.8 tests failed with exit code %TEST_RC%.
  goto :failed
)

set "BACKUP=backups\phase5.8-source-before-%STAMP%"
mkdir "%BACKUP%\random_sniper" >nul 2>&1
for %%F in (live_scan_custom.py custom_input.py random_range_sniper.py live_opportunity_radar.py liveScanCustom.bat pokemonInput.txt) do (
  if exist "%%F" copy /Y "%%F" "%BACKUP%\%%F" >nul
)
if exist "random_sniper\excel_adapter.py" copy /Y "random_sniper\excel_adapter.py" "%BACKUP%\random_sniper\excel_adapter.py" >nul

call :copy_one "payload\live_scan_custom.py" ".\live_scan_custom.py"
if errorlevel 1 goto :failed
call :copy_one "payload\custom_input.py" ".\custom_input.py"
if errorlevel 1 goto :failed
call :copy_one "payload\random_range_sniper.py" ".\random_range_sniper.py"
if errorlevel 1 goto :failed
call :copy_one "payload\live_opportunity_radar.py" ".\live_opportunity_radar.py"
if errorlevel 1 goto :failed
call :copy_one "payload\random_sniper\excel_adapter.py" ".\random_sniper\excel_adapter.py"
if errorlevel 1 goto :failed
call :copy_one "payload\liveScanCustom.bat" ".\liveScanCustom.bat"
if errorlevel 1 goto :failed

if not exist "pokemonInput.txt" (
  call :copy_one "payload\pokemonInput.txt" ".\pokemonInput.txt"
  if errorlevel 1 goto :failed
  echo Created pokemonInput.txt with example rows H1810 and H1811.
) else (
  echo Preserved your existing pokemonInput.txt.
)

echo.
echo INSTALLATION SUCCESSFUL
echo Source backup: %BACKUP%
echo Test log: %CD%\%TESTLOG%
echo.
echo Edit pokemonInput.txt, close Excel, then run liveScanCustom.bat.
echo The custom scanner reads reference values only from Market Data Import column H.
echo eBay Watchlist writes remain disabled in Custom, Live and Random modes.
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
echo No workbook changes were made.
echo.
pause
endlocal & exit /b 1

:success
echo.
pause
endlocal & exit /b 0
