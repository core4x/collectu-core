@echo off
call cd .. && ^
echo App is stopping... && ^
call docker-compose down && ^
if NOT ["%errorlevel%"]==["0"] pause
pause