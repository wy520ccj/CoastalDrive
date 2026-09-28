@echo off
start "" "%~dp0..\CoastalDrive\.venv\Scripts\pythonw.exe" "%~dp0tools\environment\check_expressway.py" --play --output "%~dp0logs\HWY-01\manual-%RANDOM%-%RANDOM%"
