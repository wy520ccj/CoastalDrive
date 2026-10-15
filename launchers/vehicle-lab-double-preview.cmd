@echo off
cd /d "%~dp0.."
".venv\Scripts\python.exe" "tools\physics\run_sim_double.py" "tools\physics\vehicle_lab_double_preview.py"
