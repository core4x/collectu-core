@echo off
rem Stops the Collectu Core which start_local_background.bat started.
rem
rem Only the background processes of this installation are ended: the ones started from its virtual
rem environment. Another installation, or another Python application on this computer, keeps running.
rem A Collectu Core running in a window (start_local.bat) is stopped by closing that window.
setlocal

rem The root directory lies two levels above this script, wherever the script is started from.
for %%i in ("%~dp0..\..") do set "ROOT=%%~fi"
set "COLLECTU_PYTHONW=%ROOT%\venv\Scripts\pythonw.exe"

echo App is stopping...
rem /T ends the process tree: the pythonw.exe of a virtual environment is a launcher, and the
rem interpreter doing the work is its child.
powershell -NoProfile -Command "$found = @(Get-CimInstance Win32_Process | Where-Object { $_.ExecutablePath -eq $env:COLLECTU_PYTHONW -and $_.CommandLine -like '*main.py*' }); if (-not $found) { exit 11 }; $code = 10; foreach ($process in $found) { taskkill /PID $process.ProcessId /T /F >$null 2>&1; if ($LASTEXITCODE -ne 0) { $code = 12 } }; exit $code" 2>nul
set "RESULT=%errorlevel%"

if "%RESULT%"=="10" (
    echo App stopped.
    goto end
)
if "%RESULT%"=="11" (
    echo App is not running in the background, or it was started by another user.
    goto end
)
if "%RESULT%"=="12" (
    echo App could not be stopped. Run this script as the user who started it, or as administrator.
    goto failed
)
echo Could not look for the running app. This script needs Windows PowerShell.

:failed
echo.
pause
exit /b 1

:end
rem Leaves time to read the message, and then closes the window - also where nobody is there to press a key.
timeout /t 5 2>nul
exit /b 0
