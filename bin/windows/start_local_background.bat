@echo off
call cd .. && cd .. && ^
call cd src && ^
echo App is starting... && ^
call ..\venv\Scripts\activate.bat && ^
start pythonw main.py & ^
echo App started. && ^
pause