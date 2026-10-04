"""原固定请求持续12秒，区分稳定持续接触与接近初态。"""
from dataclasses import asdict, replace
import gzip
import hashlib
import json
from pathlib import Path
import sys

E = Path(__file__).resolve().parent
ROOT = E.parents[2]
sys.path.insert(0, str(ROOT / "src"))
from panda3d.core import Vec3
from simulation import Simulation
from vehicle_config import CAR
from vehicle_state import VehicleCommand

source = json.loads((E / "validation-r7-source-before.json").read_text(encoding="utf-8"))
assert all(hashlib.sha256((ROOT / p).read_bytes()).hexdigest() == h for p,h in source.items())
results=[]
for finite in (True,):
    s = Simulation(track="highway", traffic_count=0, config=replace(CAR, finite_drivetrain=finite))
    rows=[]
    runs=[]
    impacts=[]
    try:
        s.reset_player((6.9,30,.55))
        s.player._chassis.setLinearVelocity(Vec3(.5,8,0))
        s.player.tires.initialize_rolling(8)
        start=None
        for tick in range(1,1441):
            command=VehicleCommand(throttle=.5,steering=2,direction=1)
            s.step(command)
            snap=s.snapshot()
            contact=any(c.material=="metal_barrier" for c in snap.contacts)
            row={"tick":tick,"contact":contact,"car":asdict(snap.player),"contacts":[asdict(c) for c in snap.contacts],"impacts":[asdict(i) for i in snap.impacts],"angular_velocity":tuple(s.player._chassis.getAngularVelocity())}
            rows.append(row)
            impacts.extend(row["impacts"])
            if contact and start is None: start=tick
            if not contact and start is not None:
                runs.append([start,tick-1]); start=None
        if start is not None: runs.append([start,1440])
        name=f"rail-duration-r7-finite-{finite}.jsonl.gz"
        with gzip.open(E/name,"wt",encoding="utf-8") as f:
            for row in rows: f.write(json.dumps(row,allow_nan=False)+"\n")
        result={"finite_drivetrain":finite,"trace":name,"contact_runs":runs,"longest":max(b-a+1 for a,b in runs),"impacts":impacts,"end_car":rows[-1]["car"]}
        results.append(result)
        print(json.dumps({"finite":finite,"runs":runs,"longest":result["longest"],"impact_ticks":[i["tick"] for i in impacts],"end_position":rows[-1]["car"]["position"],"end_heading":rows[-1]["car"]["heading"],"end_speed":rows[-1]["car"]["speed"]}),flush=True)
    finally: s.close()
after={p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in source}
assert source==after
(E/"rail-duration-audit-r7.json").write_text(json.dumps({"source_before":source,"source_after":after,"source_stable":True,"scope":"native diagnosis; unchanged 600-tick threshold","results":results},indent=2)+"\n",encoding="utf-8")
