@echo off
setlocal EnableExtensions
title PokeBid - eBay Watchlist Automation
cd /d "%~dp0"

echo ==============================================================
echo PokeBid - eBay Saved Search to Watchlist Automation
echo ==============================================================
echo.
echo This launcher enables the cloud Worker schedule, loads every
echo target-labelled eBay Saved Search, accepts title matches at any price,
echo scans one UK search every two minutes with a maximum of 10 additions,
echo and refreshes the status shown here every two minutes.
echo.
echo Closing this window does NOT stop the Worker automation.
echo Press Ctrl+C only to close this status monitor.
echo.

set "PS_SCRIPT=%~dp0scripts\pokebid-watchlist-automation.ps1"
if not exist "%PS_SCRIPT%" (
  echo ERROR: Missing scripts\pokebid-watchlist-automation.ps1
  echo Extract the complete package and run this BAT again.
  echo.
  pause
  exit /b 2
)

powershell.exe -NoLogo -NoProfile -ExecutionPolicy Bypass -File "%PS_SCRIPT%" %*
set "EXIT_CODE=%ERRORLEVEL%"

echo.
if not "%EXIT_CODE%"=="0" (
  echo AUTOMATION LAUNCHER FAILED with exit code %EXIT_CODE%.
  echo Read the error above or open logs\ebay-watchlist-automation.log
) else (
  echo Status monitor closed. The cloud Worker remains enabled.
)
echo.
pause
exit /b %EXIT_CODE%
