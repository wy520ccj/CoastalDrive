@echo off
echo [HISTORICAL PACKAGE] Current source: game-current.cmd / vehicle-lab.cmd
start "" /D "%~dp0..\builds\physics-native-traffic-r9\win_amd64" "%~dp0..\builds\physics-native-traffic-r9\win_amd64\coastaldrive.exe" --vehicle-design gr86-2022-premium-6mt --driving-mode simulation
