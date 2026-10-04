"""逐拍保留Bullet原始护栏manifold，不修改接触筛选。"""
from dataclasses import replace
import json,sys
from pathlib import Path
E=Path(__file__).resolve().parent
ROOT=E.parents[2]
sys.path.insert(0,str(ROOT/"src"))
from panda3d.core import Vec3
from simulation import Simulation
from vehicle_config import CAR
from vehicle_state import VehicleCommand
s=Simulation(track="highway",traffic_count=0)
rows=[]
try:
 s.reset_player((6.9,30,.55))
 s.player._chassis.setLinearVelocity(Vec3(.5,8,0))
 s.player.tires.initialize_rolling(8)
 for tick in range(1,521):
  s.step(VehicleCommand(throttle=.5,steering=2,direction=1))
  if 500<=tick<=515:
   points=[]
   for m in s._world.getManifolds():
    a,b=m.getNode0(),m.getNode1()
    if a!=s.player._chassis and b!=s.player._chassis: continue
    other=b if a==s.player._chassis else a
    if "rail" not in other.getName(): continue
    for p in m.getManifoldPoints():
     points.append({"other":other.getName(),"distance":p.getDistance(),"impulse":p.getAppliedImpulse(),"lifetime":p.getLifeTime(),"a":tuple(p.getPositionWorldOnA()),"b":tuple(p.getPositionWorldOnB()),"normal":tuple(p.getNormalWorldOnB())})
   rows.append({"tick":tick,"position":tuple(s.player._chassis.getTransform().getPos()),"points":points})
finally: s.close()
(E/"rail-scrape-manifold-r7.json").write_text(json.dumps(rows,indent=2)+"\n",encoding="utf-8")
for r in rows:
 print(json.dumps({"tick":r["tick"],"points":[{k:p[k] for k in ("other","distance","impulse","lifetime")} for p in r["points"]]}),flush=True)
