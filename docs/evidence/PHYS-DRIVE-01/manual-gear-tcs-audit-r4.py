"""显式挡位覆盖自动方向时，核对真实TCS与原生传动输出。"""
import sys,json,hashlib
from pathlib import Path
from dataclasses import replace
ROOT=Path(__file__).resolve().parents[3]
sys.path.insert(0,str(ROOT/'src'))
sys.path.insert(0,str(ROOT/'tools'))
from driving_modes import DrivingMode
from physics.reference_ab import _create_vehicle,_step
from vehicle_state import VehicleCommand
results=[]
hashes=lambda:{p.relative_to(ROOT).as_posix():hashlib.sha256(p.read_bytes()).hexdigest() for folder in ('src','tests','tools') for p in sorted((ROOT/folder).rglob('*.py'))}
before=hashes()
for mode in DrivingMode:
 for gear in (-1,1):
  for direction in (-1,0,1):
   config=replace(mode.vehicle_config,road_friction=.35)
   world,vehicle=_create_vehicle(config)
   active=0;peak=0.;minimum=1.
   try:
    for _ in range(240):_step(world,vehicle,VehicleCommand(brake=1.))
    for tick in range(240):
     _step(world,vehicle,VehicleCommand(throttle=1.,gear=gear,clutch=1.,direction=direction))
     state=vehicle.snapshot()
     active+=state.traction_state.active
     minimum=min(minimum,state.traction_state.torque_scale)
     peak=max(peak,max(abs(w.kappa) for w in state.wheel_dynamics[2:] if w.kappa is not None))
    results.append({'mode':mode.value,'gear':gear,'direction':direction,'active_ticks':active,'minimum_scale':minimum,'peak_rear_slip':peak,'end_speed':state.speed})
    print(results[-1],flush=True)
   finally:vehicle.close()
after=hashes()
assert before==after
(ROOT/'docs/evidence/PHYS-DRIVE-01/manual-gear-tcs-audit-r4.json').write_text(json.dumps({'source_before':before,'source_after':after,'source_stable':True,'results':results},indent=2),encoding='utf-8')
