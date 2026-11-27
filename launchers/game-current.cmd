@echo off
setlocal
cd /d "%~dp0.."
set "ROAD_EDGE_SDK=%CD%\build\road-edge-sdk\panda\built-road-edge"
if exist "%ROAD_EDGE_SDK%\.road-edges-ready" set "PYTHONPATH=%ROAD_EDGE_SDK%;%PYTHONPATH%"
start "" /D "%~dp0.." "%~dp0..\.venv\Scripts\pythonw.exe" "%~dp0..\src\main.py" --driving-mode game
endlocal
