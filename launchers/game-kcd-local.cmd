@echo off
setlocal
cd /d "%~dp0.."
set "ROAD_EDGE_SDK=%CD%\build\road-edge-sdk\panda\built-road-edge"
if exist "%ROAD_EDGE_SDK%\.road-edges-ready" set "PYTHONPATH=%ROAD_EDGE_SDK%;%PYTHONPATH%"
"%~dp0..\.venv\Scripts\python.exe" "%~dp0..\tools\environment\local_kcd_drive.py"
if errorlevel 1 pause
