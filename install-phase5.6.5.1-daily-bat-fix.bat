@echo off
setlocal
cd /d "%~dp0"
chcp 65001 >nul

echo ======================================================
echo Phase 5.6.5.1 - Daily Updater BAT Fix
echo ======================================================
echo.
echo Close the daily updater window before continuing.
echo This changes only update-pokemon-market-daily.bat.
echo.

if not exist "Pokemon-Auction-Scanner-Dashboard.xlsx" (
    echo ERROR: Run this installer from the main PokemonCardTrading folder.
    echo The dashboard workbook was not found beside this BAT file.
    goto :failed
)

if not exist "update_pokemon_market.py" (
    echo ERROR: update_pokemon_market.py was not found.
    echo Install Phase 5.6.5 first, then apply this launcher fix.
    goto :failed
)

if not exist "payload\update-pokemon-market-daily.bat" (
    echo ERROR: The payload folder is missing or incomplete.
    goto :failed
)

for /f %%I in ('powershell -NoProfile -Command "Get-Date -Format yyyyMMdd-HHmmss"') do set STAMP=%%I
set BACKUP=backups\update-pokemon-market-daily-before-5.6.5.1-%STAMP%.bat

if exist "update-pokemon-market-daily.bat" (
    if not exist "backups" mkdir "backups"
    copy /Y "update-pokemon-market-daily.bat" "%BACKUP%" >nul
)

copy /Y "payload\update-pokemon-market-daily.bat" ".\update-pokemon-market-daily.bat" >nul
if errorlevel 1 goto :failed

powershell -NoProfile -ExecutionPolicy Bypass -Command "$text = Get-Content -Raw '.\update-pokemon-market-daily.bat'; if ($text.Contains('2^>^&1') -or $text.Contains('^| Tee-Object') -or -not $text.Contains('2>&1 | Tee-Object')) { exit 1 }"
if errorlevel 1 (
    echo ERROR: The corrected launcher failed its installation check.
    goto :failed
)

echo.
echo INSTALLATION SUCCESSFUL
if defined STAMP echo Previous launcher backup: %BACKUP%
echo.
echo Next run:
echo   update-pokemon-market-daily.bat
goto :end

:failed
echo.
echo INSTALLATION FAILED. Review the message above.
exit /b 1

:end
echo.
pause
endlocal
