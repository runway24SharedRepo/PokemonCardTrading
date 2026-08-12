@echo off
setlocal
cd /d "%~dp0"
chcp 65001 >nul
set PYTHONUTF8=1
set PYTHONUNBUFFERED=1

echo ======================================================
echo Phase 5.7 - On-Demand Cardmarket 30-Day Pricing
echo ======================================================
echo.
echo Close Pokemon-Auction-Scanner-Dashboard.xlsx and all scanner BAT files.
echo.

if not exist "Pokemon-Auction-Scanner-Dashboard.xlsx" (
  echo ERROR: Run this installer from the main PokemonCardTrading folder.
  echo The dashboard workbook was not found beside this BAT file.
  goto :failed
)

if not exist "payload\on_demand_pricing.py" (
  echo ERROR: The Phase 5.7 payload is missing or incomplete.
  goto :failed
)

for /f %%I in ('powershell -NoProfile -Command "Get-Date -Format yyyyMMdd-HHmmss"') do set STAMP=%%I
set BACKUP=backups\phase5.7-source-before-%STAMP%
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

copy /Y "payload\on_demand_pricing.py" ".\on_demand_pricing.py" >nul
copy /Y "payload\live_opportunity_radar.py" ".\live_opportunity_radar.py" >nul
copy /Y "payload\random_range_sniper.py" ".\random_range_sniper.py" >nul
copy /Y "payload\seller_radar.py" ".\seller_radar.py" >nul
copy /Y "payload\long_term_excel.py" ".\long_term_excel.py" >nul
copy /Y "payload\seller_radar_excel.py" ".\seller_radar_excel.py" >nul
copy /Y "payload\live_radar\excel_adapter.py" ".\live_radar\excel_adapter.py" >nul
copy /Y "payload\random_sniper\excel_adapter.py" ".\random_sniper\excel_adapter.py" >nul
copy /Y "payload\random_sniper\core.py" ".\random_sniper\core.py" >nul
copy /Y "payload\market_updater\api.py" ".\market_updater\api.py" >nul
copy /Y "payload\market_updater\pricing.py" ".\market_updater\pricing.py" >nul

if exist ".venv\Scripts\python.exe" (
  ".venv\Scripts\python.exe" -m py_compile on_demand_pricing.py live_opportunity_radar.py random_range_sniper.py seller_radar.py live_radar\excel_adapter.py random_sniper\excel_adapter.py random_sniper\core.py long_term_excel.py seller_radar_excel.py
  if errorlevel 1 goto :failed
  ".venv\Scripts\python.exe" "tests\test_on_demand_pricing.py"
) else (
  py -3 -m py_compile on_demand_pricing.py live_opportunity_radar.py random_range_sniper.py seller_radar.py live_radar\excel_adapter.py random_sniper\excel_adapter.py random_sniper\core.py long_term_excel.py seller_radar_excel.py
  if errorlevel 1 goto :failed
  py -3 "tests\test_on_demand_pricing.py"
)
if errorlevel 1 goto :failed

echo.
echo INSTALLATION SUCCESSFUL
echo Source backup: %BACKUP%
echo.
echo Market Data Import column H is no longer used by Live Radar,
echo Random Range Sniper or Seller Radar.
echo Start a normal scan; a daily market-table refresh is not required.
goto :end

:failed
echo.
echo INSTALLATION FAILED. Review the message above.
exit /b 1

:end
echo.
pause
endlocal

