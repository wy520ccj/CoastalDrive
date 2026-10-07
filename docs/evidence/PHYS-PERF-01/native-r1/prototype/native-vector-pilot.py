"""只在本进程比较原生向量内核；生产源码与依赖保持。"""
import importlib
import json
import sys
from pathlib import Path

root = Path(__file__).resolve().parents[3]
folder = Path(__file__).resolve().parent
sys.path[:0] = [str(folder / 'native-lib'), str(root / 'src')]
import _port_probe

dynamic = ('driveline_inertia', 'differential', 'suspension', 'shaft_transmission', 'tire_drivetrain')
spatial = ('rotor_dynamics', 'suspension_kinematics', 'transmission_ports',
           'triangle_support', 'wheel_envelope', 'tire_coupling')
for name in dynamic:
    module = importlib.import_module(name)
    module.dot = _port_probe.dot
for name in spatial:
    module = importlib.import_module(name)
    module.dot = _port_probe.dot3
    if name != 'wheel_envelope':
        module.cross = _port_probe.cross
import tire_drivetrain
tire_drivetrain.cross = _port_probe.cross
tire_drivetrain.shaft_brake_state = _port_probe.shaft_brake_state
script = folder / 'compare_ticks.py'
sys.argv = [str(script), str(folder / 'native-vector-pilot-snapshots.json')]
exec(compile(script.read_text(encoding='utf-8'), str(script), 'exec'), {'__file__': str(script)})
result = {'in_memory_only': True, 'status': 'completed', 'vector_modules': [*dynamic, *spatial],
          'floating_point_flags': ['/fp:strict', '/utf-8']}
(folder / 'native-vector-pilot.json').write_text(json.dumps(result, indent=2))
print(json.dumps(result))
