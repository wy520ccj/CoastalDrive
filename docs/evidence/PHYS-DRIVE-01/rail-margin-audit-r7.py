"""只在起始时设置Box内部margin，核对接触连续性与名义外廓。"""
from dataclasses import replace
import json,sys
from pathlib import Path
E=Path(__file__).resolve().parent;ROOT=E.parents[2]
sys.path.insert(0,str(ROOT/"src"))
from panda3d.core import Vec3
from simulation import Simulation
from vehicle_state import VehicleCommand
results=[]
for margin in (.001,.01,.04):
 s=Simulation(track="highway",traffic_count=0)
 try:
  s.reset_player((6.9,30,.55))
  s.player._chassis.setLinearVelocity(Vec3(.5,8,0));s.player.tires.initialize_rolling(8)
  geometry=[]
  for i in range(s.player._chassis.getNumShapes()):
   shape=s.player._chassis.getShape(i)
   before=tuple(shape.getHalfExtentsWithMargin())
   shape.setMargin(margin)
   geometry.append({"before":before,"after":tuple(shape.getHalfExtentsWithMargin()),"margin":shape.getMargin()})
  runs=[];start=None;impacts=[];max_pitch=0
  for tick in range(1,841):
   s.step(VehicleCommand(throttle=.5,steering=2,direction=1))
   snap=s.snapshot();contact=any(c.material=="metal_barrier" for c in snap.contacts)
   impacts.extend(i.tick for i in snap.impacts);max_pitch=max(max_pitch,abs(snap.player.pitch))
   if contact and start is None:start=tick
   if not contact and start is not None:runs.append([start,tick-1]);start=None
  if start is not None:runs.append([start,840])
  result={"margin":margin,"geometry":geometry,"runs":runs,"longest":max(b-a+1 for a,b in runs),"impact_ticks":impacts,"end_position":snap.player.position,"max_pitch":max_pitch}
  results.append(result);print(json.dumps(result),flush=True)
 finally:s.close()
(E/"rail-margin-audit-r7.json").write_text(json.dumps(results,indent=2)+"\n",encoding="utf-8")
