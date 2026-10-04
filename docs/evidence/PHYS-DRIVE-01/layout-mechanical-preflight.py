"""下一布局机制的独立虚功/角动量/端口台架，尚未接入生产物理。"""
import hashlib
import json
import math
from pathlib import Path
import random
import sys

E=Path(__file__).resolve().parent;ROOT=E.parents[2]
sys.path.insert(0,str(ROOT/"src"))
from transmission_ports import transmission_state

rng=random.Random(0)
source=json.loads((E/"validation-r8-source-before.json").read_text(encoding="utf-8"))
assert all(hashlib.sha256((ROOT/p).read_bytes()).hexdigest()==h for p,h in source.items())
inertia=(600.,1100.,1500.,.2,1.1,1.1,1.1,1.1)
engine_axis=(0.,1.,0.)
dt=1/120
records=[]
max_power=max_momentum=max_energy=0.
negative_controls=[]
for beta in (0.,.3,.5,1.):
 weights=(beta/2,beta/2,(1-beta)/2,(1-beta)/2)
 for ratio in (-13.,14.):
  for eta in (.88,1.):
   for case in range(20):
    angle=math.radians(rng.uniform(-25,25))
    tilt=math.radians(rng.uniform(-10,10))
    front_angles=(angle-math.radians(2),angle+math.radians(2))
    axes=tuple((-math.cos(a)*math.cos(tilt),math.sin(a),math.cos(a)*math.sin(tilt)) for a in front_angles)+((-1.,0.,0.),)*2
    state=tuple(rng.uniform(-80,80) for _ in inertia)
    shell=tuple(ratio*sum(weights[i]*axes[i][a] for i in range(4)) for a in range(3))
    gear=shell+(0.,)+tuple(ratio*w for w in weights)
    clutch=tuple(-engine_axis[a]-shell[a] for a in range(3))+(1.,)+tuple(-ratio*w for w in weights)
    dot=lambda a,b:sum(x*y for x,y in zip(a,b))
    relative=tuple(state[4+i]+dot(state[:3],axes[i]) for i in range(4))
    sg=ratio*sum(weights[i]*relative[i] for i in range(4))
    sc=state[3]-dot(state[:3],engine_axis)-sg
    assert math.isclose(dot(gear,state),sg,abs_tol=2e-12)
    assert math.isclose(dot(clutch,state),sc,abs_tol=2e-12)
    mc=tuple(clutch[a]/inertia[a] for a in range(8))
    mg=tuple(gear[a]/inertia[a] for a in range(8))
    response=((dot(clutch,mc),dot(clutch,mg)),(dot(gear,mc),dot(gear,mg)))
    (c,loss),(slip_end,speed_end)=transmission_state((sc,sg),response,dt,300.,eta)
    torque=tuple(-c*clutch[a]-loss*gear[a] for a in range(8))
    end=tuple(state[a]+dt*torque[a]/inertia[a] for a in range(8))
    drive=ratio*(c-loss)
    wheel_torques=tuple(w*drive for w in weights)
    assert torque[4:]==wheel_torques or max(abs(a-b) for a,b in zip(torque[4:],wheel_torques))<1e-12
    assert wheel_torques[0]==wheel_torques[1] and wheel_torques[2]==wheel_torques[3]
    power=dot(torque,end)
    heat_power=c*slip_end+loss*speed_end
    assert heat_power>=-1e-8
    power_error=abs(power+heat_power)
    momentum=tuple(torque[a]+torque[3]*engine_axis[a]-sum(torque[4+i]*axes[i][a] for i in range(4)) for a in range(3))
    momentum_error=max(abs(x) for x in momentum)
    energy_change=.5*sum(inertia[a]*(end[a]**2-state[a]**2) for a in range(8))
    numerical=.5*dt**2*sum(torque[a]**2/inertia[a] for a in range(8))
    energy_error=abs(energy_change+dt*heat_power+numerical)
    assert power_error<1e-8 and momentum_error<1e-10 and energy_error<1e-7
    max_power=max(max_power,power_error);max_momentum=max(max_momentum,momentum_error);max_energy=max(max_energy,energy_error)
    if beta==0:
     old_shell=tuple(ratio/2*(axes[2][a]+axes[3][a]) for a in range(3))
     assert shell==old_shell
     assert clutch==tuple(-engine_axis[a]-old_shell[a] for a in range(3))+(1.,0.,0.,-ratio/2,-ratio/2)
    if beta>0 and abs(drive)>1:
     missing=tuple(-drive*sum(weights[i]*axes[i][a] for i in (0,1)) for a in range(3))
     assert max(abs(x) for x in missing)>1e-3
     negative_controls.append(max(abs(x) for x in missing))
    records.append({"beta":beta,"ratio":ratio,"efficiency":eta,"case":case,"steering_deg":math.degrees(angle),"front_angles_deg":tuple(math.degrees(a) for a in front_angles),"state":state,"weights":weights,"clutch_torque":c,"loss_torque":loss,"wheel_torques":wheel_torques,"power_error_W":power_error,"momentum_rate_error_Nm":momentum_error,"energy_error_J":energy_error})
after={p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in source}
assert source==after
receipt={"scope":"independent next-layout preflight; production remains RWD, no tire/TCS/lifecycle acceptance","cases":len(records),"negative_front_reaction_controls":len(negative_controls),"min_negative_momentum_error_Nm":min(negative_controls),"max_power_error_W":max_power,"max_momentum_rate_error_Nm":max_momentum,"max_energy_error_J":max_energy,"source_stable":True,"source_before":source,"source_after":after,"records":records}
(E/"layout-mechanical-preflight.json").write_text(json.dumps(receipt,indent=2)+"\n",encoding="utf-8")
print(json.dumps({k:v for k,v in receipt.items() if k not in ("records","source_before","source_after")}))
