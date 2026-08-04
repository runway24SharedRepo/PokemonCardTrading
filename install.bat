@echo off
cd /d "%~dp0"
py -m venv .venv
call .venv\Scripts\activate
python -m pip install --upgrade pip
pip install -r requirements.txt
if not exist .env copy .env.example .env
echo.
echo Installation complete. Run run-demo.bat before live mode.
pause
