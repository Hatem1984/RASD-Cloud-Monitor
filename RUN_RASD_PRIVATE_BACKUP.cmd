@echo off
setlocal
cd /d "%~dp0"
title RASD | AES-256-GCM Encrypted Backup
if not defined RASD_PRIVATE_DATA set "RASD_PRIVATE_DATA=%LOCALAPPDATA%\RASD-Customer-Trial"
set "ARCHIVE_DIR=%LOCALAPPDATA%\RASD-Enterprise-Encrypted-Backups"
set "KEY_DIR=%LOCALAPPDATA%\RASD-Recovery-Keys-KEEP-SEPARATE"
if not exist "%ARCHIVE_DIR%" mkdir "%ARCHIVE_DIR%"
if not exist "%KEY_DIR%" mkdir "%KEY_DIR%"
for /f %%I in ('powershell -NoProfile -Command "Get-Date -Format yyyyMMdd-HHmmssfff"') do set "STAMP=%%I"
echo RASD: creating AES-256-GCM private backup. Key stays in a DIFFERENT folder.
echo Close the local trial before backing up; no scan or report may be running.
echo Data: %RASD_PRIVATE_DATA%
choice /C YN /M "Confirm this private trial is closed and idle"
if errorlevel 2 exit /b 2
py -3 -m rasd_app.encrypted_backup create --data "%RASD_PRIVATE_DATA%" --out "%ARCHIVE_DIR%\RASD-%STAMP%.rasd.enc" --key-file "%KEY_DIR%\RASD-%STAMP%.key"
if errorlevel 1 (echo Encrypted backup FAILED. Check the displayed error.& pause & exit /b 1)
echo.
echo BACKUP SUCCESS. Encrypted archive: %ARCHIVE_DIR%\RASD-%STAMP%.rasd.enc
echo RESTORE KEY: %KEY_DIR%\RASD-%STAMP%.key
echo Protect both; never upload your recovery key or store it beside the archive.
pause
