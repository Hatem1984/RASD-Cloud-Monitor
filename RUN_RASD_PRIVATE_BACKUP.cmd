@echo off
setlocal
cd /d "%~dp0"
title RASD Verified Private Backup
set "DAT=%LOCALAPPDATA%\RASD-Enterprise-Private-20261123"
set "OUT=%LOCALAPPDATA%\RASD-Enterprise-Backups"
if not exist "%OUT%" mkdir "%OUT%"
for /f %%I in ('powershell -NoProfile -Command "Get-Date -Format yyyyMMdd-HHmmss"') do set "STAMP=%%I"
echo Creating private backup. In-flight scans block backup.
py -3 -m rasd_app.backup create --data "%DAT%" --out "%OUT%\RASD-%STAMP%.zip"
if errorlevel 1 (echo Backup failed HOLD.& pause & exit /b 1)
echo Private backup verified in %OUT%
pause
