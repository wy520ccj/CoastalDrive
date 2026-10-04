"""冻结生产版本上的悬架SI映射核对，只改变明确研究配置。"""
from dataclasses import asdict, replace
import gzip,hashlib,json
from pathlib import Path
import statistics
import sys
E=Path(__file__).resolve().parent;ROOT=E.parents[2]
sys.path.insert(0,str(ROOT/"src"));sys.path.insert(0,str(ROOT/"tools"))
from driving_modes import DrivingMode
from physics.reference_ab import _create_vehicle,_step
from vehicle_state import VehicleCommand

source=json.loads((E/"validation-r8-source-before.json").read_text(encoding="utf-8"))
assert all(hashlib.sha256((ROOT/p).read_bytes()).hexdigest()==h for p,h in source.items())
results=[]
for mode in ("game","simulation"):
 base=DrivingMode(mode).vehicle_config
 si=(base.mass*base.suspension_stiffness,base.mass*base.suspension_compression,base.mass*base.suspension_relaxation)
 for mass in (1200.,1800.):
  for scheme in ("normalized","fixed-si"):
   inertia=None if base.body_inertia is None else tuple(v*mass/base.mass for v in base.body_inertia)
   config=replace(base,mass=mass,body_inertia=inertia)
   if scheme=="fixed-si":
    config=replace(config,suspension_stiffness=si[0]/mass,suspension_compression=si[1]/mass,suspension_relaxation=si[2]/mass)
   world,car=_create_vehicle(config);rows=[];max_force_error=0.;branches=set()
   try:
    for tick in range(1,601):
     _step(world,car,VehicleCommand(gear=0))
     snap=car.snapshot();native=[]
     for i,wheel in enumerate(car._vehicle.getWheels()):
      c=snap.wheel_contacts[i];v=wheel.getSuspensionRelativeVelocity();clip=wheel.getClippedInvConnectionPointCs()
      damping=config.suspension_compression if v<0 else config.suspension_relaxation
      predicted=max(0.,mass*(config.suspension_stiffness*c.compression*clip-damping*v)) if c.in_contact else 0.
      error=abs(c.suspension_force-predicted);max_force_error=max(max_force_error,error)
      if c.in_contact and abs(v)>1e-3:branches.add("compression" if v<0 else "relaxation")
      native.append({"relative_velocity":v,"contact_factor":clip,"predicted_force_N":predicted,"force_error_N":error})
     rows.append({"tick":tick,"car":asdict(snap),"native_suspension":native})
    tail=rows[-120:]
    compression=statistics.mean(c["compression"] for r in tail for c in r["car"]["wheel_contacts"])
    load=statistics.mean(sum(c["normal_load"] for c in r["car"]["wheel_contacts"]) for r in tail)
    effective_k=mass*config.suspension_stiffness
    expected=mass*9.81/(4*effective_k)
    assert max_force_error<.01,(mode,mass,scheme,max_force_error)
    assert abs(compression-expected)<.001,(compression,expected)
    assert abs(load-mass*9.81)/(mass*9.81)<.01
    assert branches=={"compression","relaxation"},branches
    name=f"suspension-si-{mode}-{int(mass)}-{scheme}.jsonl.gz"
    with gzip.open(E/name,"wt",encoding="utf-8") as f:
     for r in rows:f.write(json.dumps(r,allow_nan=False)+"\n")
    result={"mode":mode,"mass_kg":mass,"scheme":scheme,"ticks":len(rows),"spring_N_per_m":effective_k,"compression_damping_Ns_per_m":mass*config.suspension_compression,"relaxation_damping_Ns_per_m":mass*config.suspension_relaxation,"expected_compression_m":expected,"mean_compression_m":compression,"mean_total_load_N":load,"max_raw_force_formula_error_N":max_force_error,"damping_branches":sorted(branches),"trace":name}
    results.append(result);print(json.dumps(result),flush=True)
   finally:car.close()
after={p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in source}
assert source==after
(E/"suspension-si-preflight.json").write_text(json.dumps({"scope":"read-only native parameter mapping; no production SI or antiroll implementation","source_before":source,"source_after":after,"source_stable":True,"results":results,"formula_source":"https://raw.githubusercontent.com/bulletphysics/bullet3/master/src/BulletDynamics/Vehicle/btRaycastVehicle.cpp"},indent=2)+"\n",encoding="utf-8")
