@echo off
setlocal
cd /d "%~dp0"

if not exist ".env" type nul > .env
notepad ".env"
endlocal
