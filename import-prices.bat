@echo off
cd /d "%~dp0"
call .venv\Scripts\activate
set /p CSV=Full path to HoloDex CSV:
python import_prices.py "%CSV%"
pause
