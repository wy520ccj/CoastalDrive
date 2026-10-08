"""整合真实端口精度修复的相关T1，不复用旧物理轨迹结果。"""
import json
import subprocess
import sys
from pathlib import Path
root=Path.cwd()
base=json.loads((root/'docs/evidence/PHYS-PERF-01/wheel-derivatives-r1/validation/PHYS-PERF-01-wheel-derivatives-T1/summary.json').read_text(encoding='utf-8'))
tests=base['tests']+['tests/test_impact_events.py','tests/test_h1_vehicle.py::test_collision_wall_stops_car_without_tunneling']
raise SystemExit(subprocess.call([sys.executable,'tools/validate.py','T1','--tests',*tests,
    '--output','logs/validation/PHYS-INTEGRATE-04-wall-T1']))
