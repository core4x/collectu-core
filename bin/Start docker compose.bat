@echo off
cd .. && ^
echo App is starting... && ^
call docker-compose up -d && ^
if NOT ["%errorlevel%"]==["0"] pause
pause