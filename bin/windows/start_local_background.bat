@echo off
rem Starts Collectu Core in the background, without a window. Arguments are passed on to main.py.
rem Stop it with stop_local_background.bat. What it logs is found in the 'logs' folder.
setlocal
title Collectu Core

rem The root directory lies two levels above this script, wherever the script is started from.
for %%i in ("%~dp0..\..") do set "ROOT=%%~fi"
set "PYTHON=%ROOT%\venv\Scripts\python.exe"
set "PYTHONW=%ROOT%\venv\Scripts\pythonw.exe"

if not exist "%PYTHONW%" (
    echo The virtual environment was not found. Run install_local.bat first.
    goto failed
)
cd /d "%ROOT%\src" || goto failed

rem Not an error: this script is also what an autostart entry runs, which may find the app running.
call :instance_running
if "%RUNNING%"=="yes" (
    echo Collectu Core of this installation is already running.
    goto end
)

echo App is starting...
start "" "%PYTHONW%" main.py %*

rem Without a window, a start which fails goes unseen. So look again after a moment.
timeout /t 5 /nobreak >nul 2>&1 || ping -n 6 127.0.0.1 >nul
call :instance_running
if "%RUNNING%"=="no" (
    echo App failed to start. See the log files in the 'logs' folder, or run start_local.bat to watch it.
    goto failed
)
echo App started. Stop it with stop_local_background.bat.

:end
rem Leaves time to read the message, and then closes the window - also where nobody is there to press a key.
timeout /t 5 2>nul
exit /b 0

:failed
echo.
pause
exit /b 1

rem Sets RUNNING to 'yes' if a Collectu Core of this installation is running - in a window (python.exe)
rem or in the background (pythonw.exe) -, to 'no' if none is, and to 'unknown' without PowerShell.
rem Only processes started from this installation's virtual environment count, so another
rem installation or another Python application on this computer is none.
:instance_running
set "RUNNING=unknown"
set "COLLECTU_PYTHON=%PYTHON%"
set "COLLECTU_PYTHONW=%PYTHONW%"
powershell -NoProfile -Command "if (Get-CimInstance Win32_Process | Where-Object { ($env:COLLECTU_PYTHON, $env:COLLECTU_PYTHONW) -contains $_.ExecutablePath -and $_.CommandLine -like '*main.py*' }) { exit 10 } else { exit 11 }" 2>nul
set "RESULT=%errorlevel%"
if "%RESULT%"=="10" set "RUNNING=yes"
if "%RESULT%"=="11" set "RUNNING=no"
exit /b 0
