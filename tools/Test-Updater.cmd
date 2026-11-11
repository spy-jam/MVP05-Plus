@echo off
rem Tries the Launcher's updater on your private test release: see Test-Updater.ps1
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0Test-Updater.ps1" %*
echo.
pause
