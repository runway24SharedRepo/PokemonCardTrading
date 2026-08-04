@echo off
cd /d "%~dp0"
call .venv\Scripts\activate
echo Python executable:
where python
python --version
echo.
python -m unittest discover -s tests -v
pause
