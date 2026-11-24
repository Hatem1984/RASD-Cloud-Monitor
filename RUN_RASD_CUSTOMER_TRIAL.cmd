@echo off
setlocal
cd /d "%~dp0"
title RASD - Private Institutional Trial (MANUAL)
if not defined RASD_PRIVATE_DATA set "RASD_PRIVATE_DATA=%LOCALAPPDATA%\RASD-Customer-Trial"
if not defined RASD_PRIVATE_PORT set "RASD_PRIVATE_PORT=8774"
set "RASD_PRIVATE_URL=http://127.0.0.1:%RASD_PRIVATE_PORT%"
set "PLAYWRIGHT_BROWSERS_PATH=%~dp0.venv-trial\pw-browsers"
set "PLAYWRIGHT_SKIP_BROWSER_GC=1"
echo RASD PRIVATE LIVE - MANUAL - NO SMTP / SCHEDULES
echo Data: %RASD_PRIVATE_DATA%
powershell -NoProfile -Command "try {$r=Invoke-RestMethod ($env:RASD_PRIVATE_URL+'/api/health') -TimeoutSec 2; if($r.service -eq 'RASD Manual' -and $r.private_live -and $r.scheduler -eq 'DISABLED_IN_THIS_APP' -and $r.email -eq 'NOT_IMPLEMENTED') {exit 0}; exit 2} catch {exit 1}"
if not errorlevel 1 (
  echo A private RASD instance already responds on this configured port.
  start "" "%RASD_PRIVATE_URL%"
  exit /b 0
)
if %errorlevel% EQU 2 (echo PORT occupied by an unexpected app. HOLD.& pause & exit /b 2)
where py >nul 2>&1
if errorlevel 1 (echo Python 3.11 or newer required.& pause & exit /b 1)
if not exist ".venv-trial\Scripts\python.exe" (
  py -3 -m venv .venv-trial
  if errorlevel 1 (echo Virtual environment creation FAILED.& pause & exit /b 1)
)
".venv-trial\Scripts\python.exe" -m pip install -r requirements-enterprise.txt
if errorlevel 1 (echo Installation FAILED.& pause & exit /b 1)
".venv-trial\Scripts\python.exe" -m playwright install chromium
if errorlevel 1 (echo Browser unavailable. Capture remains HOLD.& pause & exit /b 1)
echo Private first-owner file: %RASD_PRIVATE_DATA%\OWNER_LOGIN_LOCAL.txt
echo No account is reset if the private database already exists.
start "" /min cmd /c "timeout /t 4 /nobreak >nul && start %RASD_PRIVATE_URL%"
".venv-trial\Scripts\python.exe" -m rasd_app.server --private-live --init-owner --data "%RASD_PRIVATE_DATA%" --host 127.0.0.1 --port %RASD_PRIVATE_PORT%
echo RASD stopped.
pause
