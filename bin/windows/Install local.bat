@echo off
call cd .. && ^
if NOT ["%errorlevel%"]==["0"] pause
echo Create virtual environment 'venv'. && ^
if NOT ["%errorlevel%"]==["0"] pause
call python -m venv venv && ^
if NOT ["%errorlevel%"]==["0"] pause
echo Activate virtual environment. && ^
if NOT ["%errorlevel%"]==["0"] pause
call venv\Scripts\activate.bat && ^
if NOT ["%errorlevel%"]==["0"] pause
echo Install requirements. && ^
if NOT ["%errorlevel%"]==["0"] pause
call venv\Scripts\pip install -r src\requirements.txt && ^
if NOT ["%errorlevel%"]==["0"] pause
call venv\Scripts\deactivate.bat && ^
echo Installation successfully finished. && ^
pause