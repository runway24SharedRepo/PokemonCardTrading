@echo off
cd /d "%~dp0"
call .venv\Scripts\activate
python database_self_test.py
if errorlevel 1 (
  echo.
  echo Database self-test failed.
)
pause
