@echo off
setlocal
cd /d "%~dp0"
chcp 65001 >nul
set PYTHONUTF8=1

echo ======================================================
echo Configure OpenAI API Key
echo ======================================================
echo.
echo The key is stored only in the local .env file.
echo It is not written into Excel.
echo.

if not exist ".venv\Scripts\python.exe" (
    echo ERROR: Existing scanner Python environment was not found.
    goto :end
)

".venv\Scripts\python.exe" configure_openai_env.py

:end
echo.
pause
endlocal
