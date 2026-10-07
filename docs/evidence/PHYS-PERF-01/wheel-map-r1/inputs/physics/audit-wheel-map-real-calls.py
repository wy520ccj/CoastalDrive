import json
import subprocess
import sys
import textwrap
import types
from pathlib import Path

root=Path.cwd();sys.path.insert(0,str(root/'src'))
import tire_drivetrain as target
source=subprocess.run(['git','show','105d849:src/tire_drivetrain.py'],capture_output=True,text=True,encoding='utf-8',check=True).stdout
shared_ctor,load_ctor,ctor,state_fn=target.shared_map_coefficients,target.load_coefficients,target.wheel_map_coefficients,target.wheel_map_state
shared_args={};load_args={};spaces={};counts={'calls':0,'hard_gear':0,'synchronizing':0,'warm_updates':0,'multiple_attempts':0}
blocks=[]
for begin,end in [('    def branch_free(', '    def bias_limits('),('        def local_state(', '        def residual(')]:
    blocks.append(textwrap.dedent(source[source.index(begin):source.index(end,source.index(begin))]))
def shared(*args):
    packet=shared_ctor(*args);shared_args[id(packet)]=args;return packet
def loaded(*args):
    packet=load_ctor(*args);load_args[id(packet)]=args;return packet
def prepared(*args):
    packet=ctor(*args)
    shared_packet,load_packet,branches,brake_gradients,brakes=args
    mass,spin,base,_branches,ports,differential,damping,limits,differential_responses,dt,capacity,efficiency,synchronizer,hard,rolling,bias=shared_args[id(shared_packet)]
    responses,_tangents,_axles,_dt,mass_value,dimensions=load_args[id(load_packet)]
    space=dict(target.__dict__)
    space.update(dimensions=9,shaft=True,hard_gear=hard,limited=any(c and l for c,l in zip(damping,limits)),
                 torque_bias=any(b>1 for b in bias[3]),branches=branches,brake_gradients=brake_gradients,brakes=brakes,
                 clutch_gradient=ports[0],shaft_gear_gradient=ports[1],gear_gradient=ports[2] if hard else None,
                 differential=differential,damping=damping,differential_responses=differential_responses,
                 dt=dt,capacity=capacity,efficiency=efficiency,synchronizer_capacity=synchronizer,mass=mass_value,
                 ratio=bias[0],responses=responses)
    for block in blocks:exec(compile(block,'105d849 original wheel local_state','exec'),space)
    spaces[id(packet)]=space
    return packet
def states(packet,wheel,base,velocity,fx,fy,limits,warm,modes,tangent,axle):
    space=spaces[id(packet)];old=[row[:] for row in modes]
    space.update(i=wheel,free_base_wheel=base,velocity_base=velocity,active_limits=limits,
                 warm_branches=[warm]*4,warm_modes=[row[:] for row in modes],
                 frame=types.SimpleNamespace(tangent=tangent,axle=axle),rx=space['responses'][wheel][0],ry=space['responses'][wheel][1])
    expected=space['local_state'](fx,fy)
    actual=state_fn(packet,wheel,base,velocity,fx,fy,limits,warm,modes,tangent,axle)
    assert actual==expected,(actual,expected)
    assert modes==space['warm_modes'],(modes,space['warm_modes'])
    updates=sum(a[wheel]!=b[wheel] for a,b in zip(old,modes))
    counts['calls']+=1;counts['hard_gear' if space['hard_gear'] else 'synchronizing']+=1
    counts['warm_updates']+=updates;counts['multiple_attempts']+=updates>1
    return actual
target.shared_map_coefficients=shared;target.load_coefficients=loaded
target.wheel_map_coefficients=prepared;target.wheel_map_state=states
import pytest
code=pytest.main(['-q','-x','tests/test_drivetrain_jacobian.py','tests/test_tire_shaft.py','tests/test_differential.py'])
report={'passed':code==0,'baseline':'105d849 original Python wheel local_state','exact_actual_calls':counts}
(root/'logs/physics/PHYS-PERF-01/wheel-map-real-call-audit.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
print(json.dumps(report));raise SystemExit(code)
