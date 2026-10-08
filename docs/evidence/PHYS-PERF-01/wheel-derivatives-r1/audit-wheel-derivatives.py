"""逐值对照原Python活动分区导数；原末状态输入独立读入两份方程。"""
import inspect
import json
import subprocess
import sys
import textwrap
from pathlib import Path

root=Path.cwd(); folder=root/'logs/physics/PHYS-PERF-01'
sys.path.insert(0,str(root/'src'))
import mechanical_kernels
import shaft_transmission
import tire_drivetrain

source=subprocess.check_output(['git','show','ab204a9:src/tire_drivetrain.py'],text=True,encoding='utf-8')
start=source.index('        def derivatives(fx, fy):')
end=source.index('\n        def jacobian(fx, fy):',start)
body=textwrap.dedent(source[start:end])
body=body.replace('def derivatives(fx, fy):','def reference(end, velocity_end, brake, branch_index, index):')
body=body.replace('    end, velocity_end, brake, (branch_index, index) = local_state(fx, fy)\n','')
compiled=compile(body,'ab204a9-original-wheel-derivatives','exec')
original=mechanical_kernels.wheel_map_derivatives
counts={'calls':0,'hard_gear':0,'synchronizing':0}

def hex_tree(value):
    if isinstance(value,float):return value.hex()
    return tuple(hex_tree(x) for x in value)

def audited(*args):
    frame=inspect.currentframe().f_back
    spaces=[]
    while frame is not None and frame.f_code.co_name!='advance_drivetrain':
        spaces.append(frame.f_locals);frame=frame.f_back
    assert frame is not None
    space=dict(tire_drivetrain.__dict__)
    space.update(frame.f_locals)
    for row in reversed(spaces):space.update(row)
    space['shaft_brake_response']=shaft_transmission.shaft_brake_response
    space['synchronizer_brake_response']=shaft_transmission.synchronizer_brake_response
    exec(compiled,space)
    expected=space['reference'](args[4],args[5],space['brake'],args[2],args[3])
    actual=original(*args)
    assert hex_tree(actual)==hex_tree(expected),(counts,args,actual,expected)
    counts['calls']+=1
    counts['hard_gear' if space['hard_gear'] else 'synchronizing']+=1
    return actual

tire_drivetrain.wheel_map_derivatives=audited
import pytest
code=pytest.main(['-q','tests/test_tire_drivetrain.py','tests/test_tire_shaft.py','tests/test_drivetrain_jacobian.py',
                 'tests/test_joint_suspension.py','tests/test_guardrail_suspension.py'])
if code==0:
    from simulation import Simulation,Control
    from vehicle_designs import GR86_DESIGN
    from driver_assist import GAME_INPUT
    sim=Simulation(17,track='coastal',traffic_count=8,config=GR86_DESIGN,input_config=GAME_INPUT)
    try:
        for tick in range(24):sim.step(Control(throttle=.3))
    finally:sim.close()
report={'baseline':'ab204a9 original Python analytical derivative body','pytest_code':int(code),
        'counts':counts,'all_output_hex_equal':code==0}
(folder/'wheel-derivatives-audit.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
print(json.dumps(report))
raise SystemExit(code)
