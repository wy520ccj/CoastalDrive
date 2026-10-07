import itertools,json,random,subprocess,sys
from pathlib import Path
root=Path.cwd();sys.path.insert(0,str(root/'src'))
import mechanical_kernels as native
from rotor_dynamics import cross
rng=random.Random(17)
source=subprocess.run(['git','show','8a8c36e:src/tire_drivetrain.py'],capture_output=True,text=True,encoding='utf-8',check=True).stdout
start=source.index('    def known(gyro, loads):');end=source.index('    spin_columns = None',start)
import textwrap
space={};exec(textwrap.dedent(source[start:end]),space)
known=space['known'];count=0
for shaft,rotor,downstream,suspension,rolling in itertools.product((False,True),repeat=5):
 n=9 if shaft else 8
 for scale in (1e-6,1.,1e6):
  inverse=tuple(tuple(rng.uniform(-.001,.001) for _ in range(3)) for a in range(3))
  projs=tuple((tuple(rng.uniform(-1,1) for a in range(n)),tuple(rng.uniform(-1,1) for a in range(n)),.001) for _ in range(3)) if downstream else ()
  engine_response=tuple(rng.uniform(-1,1) for a in range(n))
  mass=native.mass_coefficients(inverse,.2,.04 if shaft else None,1.12,projs,.0017,engine_response)
  axes=tuple(tuple(rng.uniform(-1,1) for a in range(3)) for i in range(4))
  gradients=tuple(tuple(rng.uniform(-1,1) for a in range(n)) for i in range(3)) if downstream else ()
  spin=native.rotor_coefficients(.2,(0.,1.,0.),1.12,axes,rotor,.04 if shaft else None,(0.,1.,0.),(.013,0.,.005) if downstream else (),gradients,((0.,1.,0.),)*3 if downstream else ())
  for _ in range(8):
   state=tuple(scale*rng.uniform(-1000,1000) for a in range(n))
   base=tuple(scale*rng.uniform(-1000,1000) for a in range(n))
   loads=(tuple(scale*rng.uniform(-1,1) for a in range(n)),tuple(scale*rng.uniform(-1,1) for a in range(n)) if suspension else (),tuple(scale*rng.uniform(-10,10) for a in range(3)))
   road=tuple(scale*rng.uniform(-100,100) for i in range(4));dt=1/240
   space.update(dimensions=n,wheel_start=5 if shaft else 4,free_base=base,dt=dt,rolling_active=rolling,road_torques=road,suspension=object() if suspension else None,mobility=lambda v:native.mass_response_prepared(mass,v))
   gyro=cross(native.rotor_spin_prepared(spin,state),state[:3])
   expected=known(gyro,loads)
   actual=native.known_state(mass,base,gyro,loads,dt,road if rolling else None)
   combined=native.rotor_known_state(mass,spin,base,state,loads,dt,road if rolling else None)
   assert expected==actual==combined,(shaft,rotor,downstream,suspension,rolling,scale)
   assert actual[1] is loads[2] and combined[1] is loads[2]
   assert tuple(x.hex() for x in expected[0])==tuple(x.hex() for x in combined[0])
   count+=1
report={'passed':True,'known_and_combined_cases':count,'exact_free_state_and_original_velocity_object':True,'baseline':'8a8c36e original known + validated mass/rotor numeric kernels'}
(root/'logs/physics/PHYS-PERF-01/known-state-probe.json').write_text(json.dumps(report,indent=2),encoding='utf-8');print(json.dumps(report))
