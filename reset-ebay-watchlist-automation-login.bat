@echo off
setlocal EnableExtensions
title PokeBid - Reset Automation Login
cd /d "%~dp0"

powershell.exe -NoLogo -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\pokebid-watchlist-automation.ps1" -ResetLogin
set "EXIT_CODE=%ERRORLEVEL%"
echo.
pause
exit /b %EXIT_CODE%
