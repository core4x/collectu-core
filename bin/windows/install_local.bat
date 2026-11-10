@echo off
rem Installs Collectu Core: creates the virtual environment 'venv' in the root directory and installs
rem the requirements into it. It can be run again at any time, e.g. to repair an installation.
setlocal
title Collectu Core - Installation

rem The root directory lies two levels above this script. It is not taken from the current directory:
rem "Run as administrator" starts a script in System32, a shortcut wherever it is told to.
pushd "%~dp0..\.." || goto failed

rem An environment which is there and runs is kept. One whose Python was uninstalled since is not.
"venv\Scripts\python.exe" -c "" >nul 2>&1
if not errorlevel 1 (
    echo Using the existing virtual environment 'venv'.
    goto install
)

rem Take the python on PATH, or else the py launcher. Asking for the version also tells a real Python
rem from the placeholder of the Microsoft Store, which Windows puts on PATH and which runs nothing.
set "PYTHON="
set "VERSION_CHECK=import sys; sys.exit(sys.version_info < (3, 11))"
python -c "%VERSION_CHECK%" >nul 2>&1 && set "PYTHON=python"
if not defined PYTHON py -3 -c "%VERSION_CHECK%" >nul 2>&1 && set "PYTHON=py -3"
if not defined PYTHON (
    echo Python 3.11 or newer was not found.
    echo Install it from https://www.python.org/downloads/ with the option "Add python.exe to PATH".
    goto failed
)

echo Creating the virtual environment 'venv'...
%PYTHON% -m venv venv || goto failed

:install
echo Installing the requirements...
rem The environment's interpreter is called directly, so nothing has to be activated. pip copies
rem what it installs into the environment, where the files take the permissions of the folder -
rem which is what lets several Windows users share one installation.
"venv\Scripts\python.exe" -m pip install --upgrade pip || echo Could not update pip. Continuing with the installed version.
"venv\Scripts\python.exe" -m pip install -r "src\requirements.txt" || goto failed

echo.
echo Installation successfully finished. Start the application with start_local.bat.
popd
pause
exit /b 0

:failed
echo.
echo Installation failed. See the messages above.
popd
pause
exit /b 1
