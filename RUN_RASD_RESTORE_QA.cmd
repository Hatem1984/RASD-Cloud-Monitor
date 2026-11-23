@echo off
setlocal
cd /d "%~dp0"
title RASD Isolated Restore
set "OUT=%LOCALAPPDATA%\RASD-Enterprise-Backups"
for /f "delims=" %%F in ('powershell -NoProfile -Command "(Get-ChildItem $env:LOCALAPPDATA\RASD-Enterprise-Backups\RASD-*.zip -ErrorAction SilentlyContinue | Sort-Object LastWriteTime -Descending | Select-Object -First 1).FullName"') do set "BACKUP=%%F"
if not defined BACKUP (echo No private backup found.& pause & exit /b 1)
for /f %%I in ('powershell -NoProfile -Command "Get-Date -Format yyyyMMdd-HHmmss"') do set "STAMP=%%I"
set "DEST=%LOCALAPPDATA%\RASD-Enterprise-Restore-QA-%STAMP%"
echo Restoring into independent QA directory. Existing client will remain untouched.
py -3 -m rasd_app.backup restore --archive "%BACKUP%" --out "%DEST%"
if errorlevel 1 (echo Restore failed HOLD.& pause & exit /b 1)
echo Restore verified at %DEST%
pause
