@echo off
setlocal
cd /d "%~dp0"
chcp 65001 >nul
set PYTHONUTF8=1

echo ======================================================
echo Phase 5.6.6 - Average Selling Price Authority
echo ======================================================
echo.
echo Close Pokemon-Auction-Scanner-Dashboard.xlsx first.
echo This installer does not open or change the workbook.
echo.

if not exist "Pokemon-Auction-Scanner-Dashboard.xlsx" (
    echo ERROR: Run this installer from the main PokemonCardTrading folder.
    echo The dashboard workbook was not found beside this BAT file.
    goto :failed
)

if not exist "payload\update_pokemon_market.py" (
    echo ERROR: The payload folder is missing or incomplete.
    goto :failed
)

for /f %%I in ('powershell -NoProfile -Command "Get-Date -Format yyyyMMdd-HHmmss"') do set STAMP=%%I
set BACKUP=backups\phase5.6.6-source-before-%STAMP%
mkdir "%BACKUP%\market_updater" >nul 2>&1

for %%F in (update_pokemon_market.py update-pokemon-market-daily.bat market-updater-config.json market_price_controls.py) do (
    if exist "%%F" copy /Y "%%F" "%BACKUP%\%%F" >nul
)
if exist "market_updater" xcopy /E /I /Y "market_updater\*" "%BACKUP%\market_updater\" >nul

copy /Y "payload\update_pokemon_market.py" ".\update_pokemon_market.py" >nul
copy /Y "payload\update-pokemon-market-daily.bat" ".\update-pokemon-market-daily.bat" >nul
copy /Y "payload\market-updater-config.json" ".\market-updater-config.json" >nul
copy /Y "payload\market_price_controls.py" ".\market_price_controls.py" >nul
xcopy /E /I /Y "payload\market_updater\*" ".\market_updater\" >nul

if exist ".venv\Scripts\python.exe" (
    ".venv\Scripts\python.exe" "tests\test_phase566_average_selling.py"
) else (
    py -3 "tests\test_phase566_average_selling.py"
)
if errorlevel 1 goto :failed

echo.
echo INSTALLATION SUCCESSFUL
echo Source backup: %BACKUP%
echo.
echo Next run:
echo   update-pokemon-market-daily.bat
echo.
echo The update will preserve the live workbook until a complete staging
echo workbook has been saved successfully.
echo Column H and every scanner calculation will use Cardmarket average
echo selling price after update-pokemon-market-daily.bat completes.
goto :end

:failed
echo.
echo INSTALLATION FAILED. Review the message above.
exit /b 1

:end
echo.
pause
endlocal
