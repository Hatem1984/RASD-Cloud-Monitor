@echo off
setlocal
cd /d "%~dp0"
python -B -X utf8 -m maal_web.open_competition_mvp
if errorlevel 1 (
 echo.
 echo MAAL local startup did not pass security checks. Nothing was sent.
 pause
)
endlocal
