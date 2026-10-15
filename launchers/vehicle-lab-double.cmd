@echo off
cd /d "%~dp0.."
".venv\Scripts\python.exe" "tools\physics\run_sim_double.py" "src\main.py" --lab
