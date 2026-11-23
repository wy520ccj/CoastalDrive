@echo off
cd /d "%~dp0.."
"%~dp0..\.venv\Scripts\python.exe" "%~dp0..\tools\environment\local_kcd_drive.py" --hd2-rocks --output "%~dp0..\logs\visual-upgrade-20261026\hd2-playable"
if errorlevel 1 pause
