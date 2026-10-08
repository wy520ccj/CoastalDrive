"""逐次对照原Python共同求根及全部暖状态，不替换真实力/控制/世界。"""
import inspect
import json
import subprocess
import sys
from pathlib import Path
root=Path.cwd();folder=root/'logs/physics/PHYS-PERF-01';sys.path.insert(0,str(root/'src'))
import tire_drivetrain as target
import pytest
sys.path.insert(0,str(folder/'shared-solution-baseline/b'))
import _shared_solution_old as frozen_kernel
source=subprocess.check_output(['git','show','127c1d0:src/tire_drivetrain.py'],text=True,encoding='utf-8')
begin=source.index('    def shared(guess):');end=source.index('    def velocities(',begin)
body=source[begin:end]
code='def original_factory(scope):\n'
free=('shared_branch','shared_port_index','road_torques','active_limits','bias_ports','load_terms','shaft','shared_map',
      'frames','torque_bias','bias_limits','dimensions','rolling_active','rolling_coefficients','radii','config',
      'known','spin','branches','branch_free','ratio','clutch_gradient','gear_gradient','dt','capacity',
      'efficiency','differential','damping')
for name in free:code+=f'    {name} = scope["{name}"]\n'
code+='    def shared_jacobian_columns(state):\n        return shared_map_jacobian(shared_map,state,tuple(frame.load for frame in frames),tuple(frame.supported for frame in frames),shared_branch,shared_port_index)\n'
code+=body+'    def probe(guess):\n        result=shared(guess)\n        return result, (shared_branch,shared_port_index,road_torques,active_limits,bias_ports)\n    return probe\n'
space=dict(target.__dict__)
space['shared_map_state']=frozen_kernel.shared_map_state
space['shared_map_jacobian']=frozen_kernel.shared_map_jacobian
space['_solve']=frozen_kernel.solve_lu
exec(compile(code,'127c1d0 frozen original shared root','exec'),space)
native=target.shared_solution
counts={'calls':0,'bias_calls':0,'ordinary_calls':0}
def audited(*args):
    caller=inspect.currentframe().f_back
    while caller.f_code.co_name != 'advance_drivetrain':caller=caller.f_back
    scope=dict(caller.f_locals)
    original=space['original_factory'](scope)
    old,warm=original(args[1])
    new=native(*args)
    assert old==new[:5],(counts,old,new)
    assert warm==new[5:],(counts,warm,new[5:])
    counts['calls']+=1
    counts['bias_calls' if scope['torque_bias'] else 'ordinary_calls']+=1
    return new
target.shared_solution=audited
result=pytest.main(['-q','-x','tests/test_tire_drivetrain.py','tests/test_tire_shaft.py','tests/test_drivetrain_jacobian.py','tests/test_joint_suspension.py'])
if result:raise SystemExit(result)
from simulation import Simulation,Control
from vehicle_designs import GR86_DESIGN
from driving_modes import DrivingMode
sim=Simulation(17,track='coastal',traffic_count=8,config=GR86_DESIGN,input_config=DrivingMode.GAME.input_config)
try:
    for _ in range(24):sim.step(Control(throttle=.3))
finally:sim.close()
report={'baseline':'127c1d0 original Python shared root; current native mapping/Jacobian boundaries, full root/warm audit','all_fields_equal':True,'counts':counts}
(folder/'shared-solution-independent-audit.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
print(json.dumps(report))

