@echo off
cd /d "%~dp0"
".venv\Scripts\python.exe" setup.py build_ext --inplace --build-temp builds/native-temp
if errorlevel 1 (
    pause
    exit /b 1
)
".venv\Scripts\python.exe" "src\main.py"
if errorlevel 1 pause
