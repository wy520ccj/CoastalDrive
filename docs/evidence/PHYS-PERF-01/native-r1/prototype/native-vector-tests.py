"""同一套独立机械账在内存原生探针中执行。"""
import importlib
import sys
from pathlib import Path

root = Path(__file__).resolve().parents[3]
folder = Path(__file__).resolve().parent
sys.path[:0] = [str(folder / 'native-lib'), str(root / 'src'), str(root)]
import _port_probe
import pytest

for name in ('driveline_inertia', 'differential', 'suspension', 'shaft_transmission', 'tire_drivetrain'):
    importlib.import_module(name).dot = _port_probe.dot
for name in ('rotor_dynamics', 'suspension_kinematics', 'transmission_ports',
             'triangle_support', 'wheel_envelope', 'tire_coupling'):
    module = importlib.import_module(name)
    module.dot = _port_probe.dot3
    if name != 'wheel_envelope':
        module.cross = _port_probe.cross
import shaft_transmission
import tire_drivetrain
shaft_transmission.shaft_brake_state = _port_probe.shaft_brake_state
tire_drivetrain.shaft_brake_state = _port_probe.shaft_brake_state
tire_drivetrain.cross = _port_probe.cross
sys.exit(pytest.main(['-q', 'tests/test_tire_drivetrain.py', 'tests/test_shaft_transmission.py',
    'tests/test_tire_shaft.py', 'tests/test_torque_bias.py', 'tests/test_drivetrain_jacobian.py',
    'tests/test_coastal_contact_step.py', 'tests/test_ramp_contact_step.py',
    'tests/test_driveline_inertia.py', 'tests/test_suspension_envelope.py']))
