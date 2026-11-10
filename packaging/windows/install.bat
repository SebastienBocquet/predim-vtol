@echo off
rem One-click installer of predimrc_wrapper: double-click after extracting the zip.
setlocal
if not exist "%~dp0uv.exe" goto not_extracted
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0install.ps1" %*
set "CODE=%ERRORLEVEL%"
if not "%CODE%"=="0" pause
exit /b %CODE%

:not_extracted
echo Extract the whole zip into a folder first, then double-click install.bat there.
pause
exit /b 1
