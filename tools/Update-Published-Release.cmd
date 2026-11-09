@echo off
rem Rebuilds the published release's zip and replaces it on GitHub (same version, page and notes): see Make-Test-Release.ps1.
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0Make-Test-Release.ps1" -Final -Refresh %*
echo.
pause
