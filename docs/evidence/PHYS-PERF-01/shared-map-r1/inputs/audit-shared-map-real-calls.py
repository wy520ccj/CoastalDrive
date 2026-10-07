import json,subprocess,sys,textwrap,types
from pathlib import Path
root=Path.cwd();sys.path.insert(0,str(root/'src'))
import tire_drivetrain as target
source=subprocess.run(['git','show','f4a5ae0:src/tire_drivetrain.py'],capture_output=True,text=True,encoding='utf-8',check=True).stdout
ctor,state_fn,jac_fn=target.shared_map_coefficients,target.shared_map_state,target.shared_map_jacobian
space=None;counts={'mapped':0,'jacobian':0,'hard_gear':0,'synchronizing':0,'nine':0,'eleven':0}
blocks=[]
for begin,end in [('    def branch_free(', '    def bias_limits('),('    def bias_limits(', '    forces = list('),('    def spin(', '    def load_terms('),('    def known(', '    spin_columns = None'),('    def shared_jacobian_columns(', '    def shared(guess):')]:
 text=textwrap.dedent(source[source.index(begin):source.index(end,source.index(begin))]).replace('nonlocal spin_columns','global spin_columns')
 blocks.append(text)
begin=source.index('        def mapped(state):');end=source.index('        variables = dimensions + 2',begin)
blocks.append(textwrap.dedent(source[begin:end]).replace('nonlocal shared_branch, shared_port_index, road_torques, active_limits','global shared_branch, shared_port_index, road_torques, active_limits'))
def prepared(*args):
 global space
 packet=ctor(*args)
 mass,spin,base,branches,ports,differential,damping,limits,responses,dt,capacity,efficiency,synchronizer,hard,rolling,bias=args
 ratio,share,final,biases,inertias,gradients,old=bias
 config=types.SimpleNamespace(front_drive_share=share,final_drive=final,axle_torque_bias_ratios=biases,rolling_transition_speed=rolling[2])
 space=dict(target.__dict__)
 space.update(dimensions=9,wheel_start=5,shaft=True,hard_gear=hard,torque_bias=any(b>1 for b in biases),
  limited=any(c and l for c,l in zip(damping,limits)),rolling_active=any(rolling[1]),
  mobility_coefficients=mass,spin_coefficients=spin,free_base=base,branches=branches,
  clutch_gradient=ports[0],shaft_gear_gradient=ports[1],gear_gradient=ports[2] if hard else None,
  brake_gradients=(ports[3] if hard else ports[2],),differential=differential,damping=damping,limits=limits,
  differential_responses=responses,dt=dt,capacity=capacity,efficiency=efficiency,synchronizer_capacity=synchronizer,
  radii=rolling[0],rolling_coefficients=rolling[1],ratio=ratio,config=config,inertias=inertias,gradients=gradients,
  downstream_omega=old,downstream=bool(old),spin_columns=None,road_torques=(0.,)*4,active_limits=limits,
  mobility=lambda v:target.mass_response_prepared(mass,v))
 for text in blocks:exec(compile(text,'f4a5ae0 original mapped/Jacobian','exec'),space)
 return packet
def states(packet,state,loads,wheel_loads,supported,warm):
 actual=state_fn(packet,state,loads,wheel_loads,supported,warm)
 space.update(loads=loads,frames=tuple(types.SimpleNamespace(load=f,supported=s) for f,s in zip(wheel_loads,supported)),
  suspension=object() if loads[1] else None,shared_branch=warm)
 expected=space['mapped'](state)
 assert actual[:5]==expected,(actual[:5],expected)
 assert actual[5:]==(space['shared_branch'],space['shared_port_index'],space['road_torques'],space['active_limits'])
 counts['mapped']+=1;counts['hard_gear' if space['hard_gear'] else 'synchronizing']+=1
 counts['eleven' if len(state)==11 else 'nine']+=1
 return actual
def jacobians(packet,state,loads,supported,branch,port):
 actual=jac_fn(packet,state,loads,supported,branch,port)
 space.update(frames=tuple(types.SimpleNamespace(load=f,supported=s) for f,s in zip(loads,supported)),shared_branch=branch,shared_port_index=port)
 expected=space['shared_jacobian_columns'](state)
 assert actual==expected,(actual,expected)
 counts['jacobian']+=1
 return actual
target.shared_map_coefficients=prepared;target.shared_map_state=states;target.shared_map_jacobian=jacobians
import pytest
code=pytest.main(['-q','tests/test_drivetrain_jacobian.py','tests/test_tire_shaft.py','tests/test_differential.py'])
report={'passed':code==0,'baseline':'f4a5ae0 original mapped/Jacobian; comparison instrumentation only in this process','exact_actual_calls':counts}
(root/'logs/physics/PHYS-PERF-01/shared-map-real-call-audit.json').write_text(json.dumps(report,indent=2),encoding='utf-8');print(json.dumps(report));raise SystemExit(code)
