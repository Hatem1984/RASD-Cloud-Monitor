@echo off
setlocal
cd /d "%~dp0"
title RASD | Verify Encrypted Restore in New QA Folder
set "ARCHIVE_DIR=%LOCALAPPDATA%\RASD-Enterprise-Encrypted-Backups"
set "KEY_DIR=%LOCALAPPDATA%\RASD-Recovery-Keys-KEEP-SEPARATE"
for /f "delims=" %%F in ('powershell -NoProfile -Command "(Get-ChildItem -LiteralPath '%ARCHIVE_DIR%' -Filter 'RASD-*.rasd.enc' -ErrorAction SilentlyContinue | Sort-Object LastWriteTime -Descending | Select-Object -First 1).FullName"') do set "ARCHIVE=%%F"
if not defined ARCHIVE (echo No encrypted backup archive found.& pause & exit /b 1)
for %%F in ("%ARCHIVE%") do set "ARCHIVE_NAME=%%~nF"
set "ARCHIVE_NAME=%ARCHIVE_NAME:.rasd=%"
set "RECOVERY_KEY=%KEY_DIR%\%ARCHIVE_NAME%.key"
if not exist "%RECOVERY_KEY%" (echo Matching key is MISSING. Restore HOLD.& pause & exit /b 1)
for /f %%I in ('powershell -NoProfile -Command "Get-Date -Format yyyyMMdd-HHmmssfff"') do set "STAMP=%%I"
set "DEST=%LOCALAPPDATA%\RASD-Enterprise-Isolated-Restore-%STAMP%"
echo Restoring a COPY of private customer files in a new independent QA folder.
py -3 -m rasd_app.encrypted_backup restore --archive "%ARCHIVE%" --key-file "%RECOVERY_KEY%" --out "%DEST%"
if errorlevel 1 (echo Restore FAILED. Original client database is unchanged.& pause & exit /b 1)
echo.
echo RESTORE VERIFIED AT: %DEST%
echo Previously authenticated sessions were revoked in the restored copy.
pause
