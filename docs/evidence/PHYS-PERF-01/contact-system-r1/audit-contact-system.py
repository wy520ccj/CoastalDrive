"""逐次对照独立旧Python控制流与旧严格浮点DLL的全部几何输出。"""
import json
import subprocess
import sys
import types
from pathlib import Path

root = Path.cwd()
folder = root / 'logs/physics/PHYS-PERF-01'
sys.path[:0] = [str(root/'src'), str(folder/'contact-system-baseline/b')]
import suspension_kinematics as current

source = subprocess.check_output(['git','show','ab204a9:src/suspension_kinematics.py'],text=True,encoding='utf-8')
module = types.ModuleType('_old_contact_geometry')
sys.modules[module.__name__] = module
exec(source.replace('from wheel_contact_kernels import','from _contact_system_old import'),module.__dict__)
original = current.finite_contact_system
counts = {'calls':0,'cylinder':0,'mixed':0,'no_kinematics':0,'touching':0,'released':0}

def values(system):
    return (tuple(tuple(x.hex() for x in row) for row in system.gradients),
            tuple(None if x is None else x.hex() for x in system.alignment),system.touching)

def audited(*args, **kwargs):
    system = args[0]
    expected = module.finite_contact_system(*args,**kwargs)
    actual = original(*args,**kwargs)
    assert values(actual)==values(expected), (counts,args)
    counts['calls']+=1
    kind = ('no_kinematics' if system.kinematics is None else 'cylinder'
            if all(p is None or isinstance(p.surface,current.CylinderSurface) for p in system.kinematics) else 'mixed')
    counts[kind]+=1
    counts['touching']+=sum(actual.touching)
    counts['released']+=len(actual.touching)-sum(actual.touching)
    return actual

current.finite_contact_system = audited
import pytest
tests = ['tests/test_cylinder_suspension.py','tests/test_finite_suspension.py',
         'tests/test_curved_suspension.py','tests/test_joint_suspension.py',
         'tests/test_guardrail_suspension.py','tests/test_suspension_coupling.py',
         'tests/test_ramp_contact_step.py','tests/test_coastal_contact_step.py']
code=pytest.main(['-q',*tests])
if code==0:
    from simulation import Simulation,Control
    from vehicle_designs import GR86_DESIGN
    from driver_assist import GAME_INPUT
    sim=Simulation(17,track='coastal',traffic_count=8,config=GR86_DESIGN,input_config=GAME_INPUT)
    try:
        for tick in range(24):sim.step(Control(throttle=.3))
    finally:sim.close()
report={'baseline':'ab204a9 independent old Python + _contact_system_old DLL','pytest_code':int(code),
        'counts':counts,'all_output_hex_equal':code==0}
(folder/'contact-system-audit.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
print(json.dumps(report))
raise SystemExit(code)
