@echo off
rem ASCII-only wrapper: cmd mis-decodes UTF-8 batch files, so the real work
rem lives in run_new_ui.ps1 (PowerShell handles the Chinese path natively).
chcp 65001 >nul
setlocal
set "PS1=%~dp0run_new_ui.ps1"

if not exist "%PS1%" (
  echo Launcher not found: "%PS1%"
  pause
  exit /b 1
)

powershell -NoProfile -ExecutionPolicy Bypass -File "%PS1%" %*
if errorlevel 1 (
  echo.
  echo Launch failed. See logs\_localappdata\crash.log for details.
  pause
)
endlocal
