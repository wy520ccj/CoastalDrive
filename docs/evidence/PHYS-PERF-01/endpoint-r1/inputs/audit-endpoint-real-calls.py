import json
import random
import subprocess
import sys
import textwrap
from pathlib import Path
root=Path.cwd();sys.path.insert(0,str(root/'src'))
import suspension_kinematics as target
import wheel_envelope
import wheel_contact_kernels
source=subprocess.run(['git','show','155aa87:src/suspension_kinematics.py'],capture_output=True,text=True,encoding='utf-8',check=True).stdout
wheel_source=subprocess.run(['git','show','155aa87:src/wheel_envelope.py'],capture_output=True,text=True,encoding='utf-8',check=True).stdout
space=dict(target.__dict__);space['subtract']=wheel_envelope.subtract
begin=wheel_source.index('def crown_extent_secant(');end=wheel_source.index('def _segment(',begin)
exec(compile(wheel_source[begin:end],'155aa87 original crown secant','exec'),space)
begin=source.index('def cylinder_endpoint(');end=source.index('def curved_endpoint(',begin)
exec(compile(source[begin:end],'155aa87 original endpoint','exec'),space)
counts={'endpoint_calls':0,'none':0,'gradient':0,'zero_rotation':0,'crown_probes':0,'cross_face_callback':0}
kernel=target.endpoint_kernel
def face_difference(*args):
    counts['cross_face_callback']+=1
    return target.face_extension_difference(*args)
def audited(*args):
    actual=kernel(*args[:-1],face_difference)
    expected=space['cylinder_endpoint'](*args[:-1])
    assert actual==expected,(actual,expected)
    counts['endpoint_calls']+=1;counts['none' if actual is None else 'gradient']+=1
    counts['zero_rotation']+=args[6]==0.
    return actual
target.endpoint_kernel=audited
rng=random.Random(17)
for _ in range(4096):
    a0,a1=rng.uniform(-1,1),rng.uniform(-1,1)
    if counts['crown_probes']%4==0:a1=a0
    radius,width,shoulder,crown=.3+rng.random(),.1+rng.random(),.01,rng.choice((0.,.01,.03))
    values=(a0,a1,radius,width,shoulder,crown)
    actual=wheel_contact_kernels.crown_extent_secant(*values);expected=space['crown_extent_secant'](*values)
    assert actual.hex()==expected.hex(),(values,actual,expected)
    counts['crown_probes']+=1
import pytest
code=pytest.main(['-q','-x','tests/test_cylinder_suspension.py','tests/test_finite_suspension.py','tests/test_curved_suspension.py','tests/test_ramp_contact_step.py','tests/test_guardrail_suspension.py'])
if code==0:
    from simulation import Simulation,Control
    from vehicle_designs import GR86_DESIGN
    from driver_assist import GAME_INPUT
    sim=Simulation(17,track='coastal',traffic_count=8,config=GR86_DESIGN,input_config=GAME_INPUT)
    try:
        for tick in range(24):sim.step(Control(throttle=.3,steering=.02 if tick>=12 else 0.))
    finally:sim.close()
report={'passed':code==0,'baseline':'155aa87 original cylinder endpoint and Python crown secant','exact_actual_calls':counts}
(root/'logs/physics/PHYS-PERF-01/endpoint-real-call-audit.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
print(json.dumps(report));raise SystemExit(code)
