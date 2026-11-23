@echo off
setlocal
cd /d "%~dp0"
title RASD Private Enterprise Manual Trial
set "RASD_PRIVATE_DATA=%LOCALAPPDATA%\RASD-Enterprise-Private-20261123"
set "RASD_PRIVATE_URL=http://127.0.0.1:8766"
echo RASD PRIVATE LIVE - NO PRODUCTION MAIL OR SCHEDULES
powershell -NoProfile -Command "try {$r=Invoke-RestMethod 'http://127.0.0.1:8766/api/health' -TimeoutSec 2; if($r.service -eq 'RASD Manual' -and $r.private_live) {exit 0}; exit 2} catch {exit 1}"
if not errorlevel 1 (
  echo Existing PRIVATE LIVE app detected. Opening.
  start "" "%RASD_PRIVATE_URL%"
  exit /b 0
)
if %errorlevel% EQU 2 (
  echo Port 8766 occupied by different app. HOLD.
  pause
  exit /b 2
)
where py >nul 2>&1
if errorlevel 1 (echo Python 3 required.& pause & exit /b 1)
py -3 -m pip install -q -r requirements-enterprise.txt
if errorlevel 1 (echo Dependency installation failed.& pause & exit /b 1)
py -3 -m playwright install chromium
if errorlevel 1 echo Browser unavailable: publisher screenshot will remain HOLD.
start "" /min cmd /c "timeout /t 3 /nobreak >nul && start http://127.0.0.1:8766"
echo Private credentials stored inside LOCALAPPDATA on first use.
echo Previously created private owner credentials are NOT reset.
py -3 -m rasd_app.server --private-live --init-owner --data "%RASD_PRIVATE_DATA%" --host 127.0.0.1 --port 8766
echo Private RASD stopped.
pause
