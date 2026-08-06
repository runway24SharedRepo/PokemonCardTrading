@echo off
setlocal
cd /d "%~dp0"

echo ======================================================
echo Pokemon Full Market Database Updater - Installation
echo ======================================================
echo.

if not exist ".venv\Scripts\python.exe" (
    echo Existing scanner virtual environment was not found.
    echo Creating .venv...
    py -m venv .venv
    if errorlevel 1 python -m venv .venv
)

if not exist ".venv\Scripts\python.exe" (
    echo ERROR: Python virtual environment could not be created.
    goto :end
)

echo Installing market updater requirements...
".venv\Scripts\python.exe" -m pip install --upgrade pip
".venv\Scripts\python.exe" -m pip install -r requirements-market.txt

if not exist "data" mkdir data
if not exist "backups" mkdir backups

if not exist ".env" (
    echo.
    echo WARNING: .env was not found.
    echo The eBay scanner normally already has this file.
    echo Creating an empty .env file.
    type nul > .env
)

echo.
echo Installation complete.
echo.
echo A Pokemon TCG API key is optional but recommended.
echo Add this line to the existing .env file:
echo POKEMON_TCG_API_KEY=YOUR_FREE_API_KEY
echo.
echo Without a key the updater still works, but downloads more slowly.
echo.
echo Next run:
echo test-pokemon-market-connection.bat

:end
echo.
pause
endlocal
