@echo off
cd /d "%~dp0"
set TASKNAME=Pokemon Auction Scanner
set COMMAND="%~dp0run-live.bat"
schtasks /Create /F /SC HOURLY /MO 1 /TN "%TASKNAME%" /TR %COMMAND%
echo Scheduled task created to run hourly.
pause
