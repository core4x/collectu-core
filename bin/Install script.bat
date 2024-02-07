@echo off
SET GIT_ACCESS_TOKEN=
SET APP_DESCRIPTION=
SET HUB_API_ACCESS_TOKEN=

if NOT ["%errorlevel%"]==["0"] pause
echo Check if GIT is installed && ^
if NOT ["%errorlevel%"]==["0"] pause
call git --version
if NOT ["%errorlevel%"]==["0"] pause
echo Clone Collectu && ^
git clone https://oauth2:%GIT_ACCESS_TOKEN%@git@github.com:core4x/collectu.git
if NOT ["%errorlevel%"]==["0"] pause
echo Edit settings.ini && ^
if NOT ["%errorlevel%"]==["0"] pause
call cd collectu && ^
if NOT ["%errorlevel%"]==["0"] pause
for /f "usebackq delims=" %%A in ("settings.ini") do (
  if "%%A" == "hub_api_access_token =" (echo app_id = %HUB_API_ACCESS_TOKEN% >> settings.tmp
  ) else (if "%%A" == "app_description =" (echo app_description = %APP_DESCRIPTION% >> settings.tmp
  ) else (if "%%A" == "git_access_token =" (echo git_access_token = %GIT_ACCESS_TOKEN% >> settings.tmp
  ) else (echo %%A >> settings.tmp)
)))
if NOT ["%errorlevel%"]==["0"] pause
del settings.ini
if NOT ["%errorlevel%"]==["0"] pause
rename settings.tmp settings.ini
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
echo Installation successfully finished. && ^
if NOT ["%errorlevel%"]==["0"] pause
echo Starting app... && ^
call cd src && ^
start http://localhost:8282
cmd /c "python main.py &"
pause
