@echo off
echo App is stopping... && ^
call taskkill /F /FI "imagename eq pythonw.exe"
pause