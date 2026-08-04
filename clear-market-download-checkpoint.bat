@echo off
setlocal
cd /d "%~dp0"

echo This deletes only the incomplete catalogue-download checkpoint.
echo It does not delete the card database, Excel workbook, or price history.
echo.
set /p CONFIRM=Type YES to restart the next download from page 1: 
if /I not "%CONFIRM%"=="YES" goto :end

if exist "data\pokemon-tcg-download-checkpoint" (
    rmdir /s /q "data\pokemon-tcg-download-checkpoint"
    echo Checkpoint deleted.
) else (
    echo No checkpoint was found.
)

:end
echo.
pause
endlocal
