@echo off
call cd .. && cd .. && ^
call cd src && ^
:loop
echo App is starting... && ^
cmd /c "..\venv\Scripts\activate.bat & python main.py & deactivate &"
echo App crashed. Restarting... && ^
timeout /T 60
goto loop
