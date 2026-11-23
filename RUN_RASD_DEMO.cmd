@echo off
setlocal
cd /d "%~dp0"
title RASD - Local Manual Demo
echo.
echo ===============================================
echo    RASD ^| Demo Local Only ^| NO MAIL ^| NO CRON
echo ===============================================
echo.
echo Address: http://127.0.0.1:8765
echo Demo owner: owner@rasd.demo
echo Demo password: RasdLocalDemo!2026
echo PUBLIC demo-only credentials on localhost.
echo NEVER use these credentials on a real server.
echo.
rem Reuse an existing localhost demo: second click must not start another
rem process or waste time installing dependencies again.
powershell -NoProfile -Command "try { $h=Invoke-RestMethod -Uri 'http://127.0.0.1:8765/api/health' -TimeoutSec 2; if($h.service -eq 'RASD Manual') { exit 0 } else { exit 1 } } catch { exit 1 }"
if not errorlevel 1 (
  echo Existing RASD local demo detected. Opening browser.
  start "" "http://127.0.0.1:8765"
  exit /b 0
)
where py >nul 2>&1
if errorlevel 1 (
  echo Python 3 required. Install from https://www.python.org/downloads/
  pause
  exit /b 1
)
if not exist ".venv\Scripts\python.exe" (
  echo Installing isolated Python environment...
  py -3 -m venv .venv
  if errorlevel 1 (echo Python setup failed.& pause & exit /b 1)
)
".venv\Scripts\python.exe" -m pip install --quiet -r requirements-test.txt
if errorlevel 1 (echo Dependencies failed to install.& pause & exit /b 1)
set "RASD_DEMO_DATA=%LOCALAPPDATA%\RASD-Manual-Client-Demo"
start "" /min cmd /c "timeout /t 3 /nobreak >nul && start http://127.0.0.1:8765"
".venv\Scripts\python.exe" -m rasd_app.server --seed-demo --data "%RASD_DEMO_DATA%" --owner-email owner@rasd.demo --owner-password "RasdLocalDemo!2026" --host 127.0.0.1 --port 8765
echo.
echo The local RASD server has stopped.
pause
