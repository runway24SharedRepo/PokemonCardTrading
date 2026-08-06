@echo off
setlocal EnableExtensions
cd /d "%~dp0"
chcp 65001 >nul
set PYTHONUTF8=1
set PYTHONUNBUFFERED=1

echo ======================================================
echo Long-Term Portfolio and Dashboard Refresh
echo ======================================================
echo.
echo Refreshes Portfolio Vault market references, long-term ratings,
echo concentration tables and the Long-Term Dashboard without running eBay.
echo.
echo Close Pokemon-Auction-Scanner-Dashboard.xlsx before continuing.
echo.

if not exist ".venv\Scripts\python.exe" (
    echo ERROR: Existing scanner Python environment was not found.
    goto :end
)

".venv\Scripts\python.exe" -u refresh_long_term_portfolio.py
set EXITCODE=%ERRORLEVEL%

echo.
echo Exit code: %EXITCODE%

:end
echo.
pause
endlocal
