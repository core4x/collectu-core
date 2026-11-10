@echo off
rem Starts Collectu Core in this window and starts it again when it crashes.
rem Arguments are passed on to main.py. Closing the window stops the application.
setlocal
title Collectu Core

rem The root directory lies two levels above this script, wherever the script is started from.
for %%i in ("%~dp0..\..") do set "ROOT=%%~fi"
set "PYTHON=%ROOT%\venv\Scripts\python.exe"
set "PYTHONW=%ROOT%\venv\Scripts\pythonw.exe"
set "RESTART_DELAY=60"

if not exist "%PYTHON%" (
    echo The virtual environment was not found. Run install_local.bat first.
    goto failed
)
cd /d "%ROOT%\src" || goto failed

call :instance_running
if "%RUNNING%"=="yes" (
    echo Collectu Core of this installation is already running. Stop it first.
    goto failed
)

:loop
echo App is starting...
"%PYTHON%" main.py %*
set "EXIT_CODE=%errorlevel%"

rem The app restarts itself after an update by replacing its process. Windows can not do that: the
rem app starts a new process and ends its own, with exit code 0. The new one keeps running in this
rem window, so it is waited for here - starting the app now would put a second one beside it.
set "SUCCESSOR="
:wait_for_successor
call :instance_running
if not "%RUNNING%"=="yes" goto ended
set "SUCCESSOR=1"
timeout /t 5 /nobreak >nul 2>&1 || ping -n 6 127.0.0.1 >nul
goto wait_for_successor

:ended
rem Exit code 0 is a stop somebody asked for (Ctrl+C, or a command line option which only prints).
if "%EXIT_CODE%"=="0" if not defined SUCCESSOR (
    echo App stopped.
    exit /b 0
)
echo App stopped unexpectedly. Restarting in %RESTART_DELAY% seconds. Close the window to prevent that.
timeout /t %RESTART_DELAY% 2>nul || ping -n %RESTART_DELAY% 127.0.0.1 >nul
goto loop

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
