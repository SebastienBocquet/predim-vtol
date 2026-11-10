@echo off
rem Remove the application and its shortcut. The studies and workbooks in Documents are kept.
echo This removes predimrc_wrapper from %~dp0
echo Your studies and PredimRC workbooks in Documents are kept.
echo Press a key to continue, or close this window to cancel.
pause >nul
cd /d "%TEMP%"
powershell -NoProfile -Command "Remove-Item -Force -ErrorAction SilentlyContinue (Join-Path ([Environment]::GetFolderPath('Desktop')) 'PredimRC wrapper.lnk')"
rmdir /s /q "%~dp0" & exit /b 0
