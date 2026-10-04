"""护栏音频集成失败的原生事实与播放器决策，不改生产阈值。"""
from dataclasses import asdict,replace
from io import StringIO
import gzip,hashlib,json,sys
from pathlib import Path
E=Path(__file__).resolve().parent;ROOT=E.parents[2]
sys.path.insert(0,str(ROOT/"src"));sys.path.insert(0,str(ROOT/"tests"))
from panda3d.core import Vec3
from test_soundscape import FakeBase,phase
from simulation import Simulation
from soundscape import Soundscape
from vehicle_config import CAR
from vehicle_state import VehicleCommand
source=json.loads((E/"validation-r8-source-before.json").read_text(encoding="utf-8"))
assert all(hashlib.sha256((ROOT/p).read_bytes()).hexdigest()==h for p,h in source.items())
results=[]
for centered,speed,finite in ((False,8,True),(True,16,True)):
 s=Simulation(track="highway",traffic_count=0,config=replace(CAR,centered_collision_support=centered,finite_drivetrain=finite))
 sound=Soundscape(FakeBase());log=StringIO();sound.set_impact_diagnostic(log)
 records=[];impacts=[];qual=[]
 try:
  s.reset_player((6.9,30,.55));s._chassis.setLinearVelocity(Vec3(1.,speed,0));s.player.tires.initialize_rolling(speed)
  for _ in range(840):
   s.step(VehicleCommand(throttle=.5,steering=3,direction=1));snap=s.snapshot()
   qualifying=any(c.material=="metal_barrier" and c.raw_impulse>=25 and c.tangential_speed>=1.6 for c in snap.contacts)
   if qualifying:qual.append(snap.tick)
   impacts.extend(asdict(i) for i in snap.impacts)
   sound.update(snap,phase("driving"),None,1/120)
   records.append({"tick":snap.tick,"car":asdict(snap.player),"contacts":[asdict(c) for c in snap.contacts],"impacts":[asdict(i) for i in snap.impacts],"qualifying":qualifying,"scrape_state":sound.impact_audio.scrape_state})
  end_driving_tick=snap.tick
  for _ in range(360):
   previous_scrape=sound.impact_audio.scrape_state
   s.step(VehicleCommand(brake=1.,steering=3,direction=1));snap=s.snapshot()
   sound.update(snap,phase("driving"),None,1/120)
   if previous_scrape=="sustain" and sound.impact_audio.scrape_state=="release":
    assert not snap.contacts or all(c.tangential_speed<1.6 for c in snap.contacts)
  assert abs(snap.player.speed)<1.6
  assert sound.impact_audio.scrape_state=="off"
  name=f"rail-audio-fixture-r8-centered-{centered}-finite-{finite}.jsonl.gz"
  with gzip.open(E/name,"wt",encoding="utf-8") as f:
   for r in records:f.write(json.dumps(r,allow_nan=False)+"\n")
  decisions=[json.loads(x) for x in log.getvalue().splitlines()]
  soundname=f"rail-audio-fixture-r8-centered-{centered}-finite-{finite}-decisions.json"
  (E/soundname).write_text(json.dumps(decisions,indent=2)+"\n",encoding="utf-8")
  result={"centered":centered,"speed":speed,"finite":finite,"impacts":impacts,"qualifying_ticks":qual,"has_consecutive_pressure":any(b==a+1 for a,b in zip(qual,qual[1:])),"hit_decisions":[r for r in decisions if r["type"]=="decision"],"scrape_transitions":[r for r in decisions if r["type"]=="scrape"],"trace":name,"sound_decisions":soundname}
  assert result["has_consecutive_pressure"]
  assert sum(bool(r.get("layers")) for r in result["hit_decisions"])==1
  assert sum(r.get("state")=="attack" for r in result["scrape_transitions"])==1
  assert any(r.get("state")=="sustain" for r in result["scrape_transitions"])
  assert any(r.get("state")=="off" for r in result["scrape_transitions"])
  result["end_driving_tick"]=end_driving_tick
  result["stopped_speed_m_s"]=snap.player.speed
  result["initial_lateral_speed_m_s"]=1.
  result["steering_degrees"]=3.
  results.append(result)
  print(json.dumps({"centered":centered,"finite":finite,"impact_ticks":[i["tick"] for i in impacts],"qualified_ticks":len(qual),"has_consecutive_pressure":result["has_consecutive_pressure"],"hits":result["hit_decisions"],"scrape_transitions":result["scrape_transitions"]}),flush=True)
 finally:sound.close();s.close()
after={p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in source};assert after==source
(E/"rail-audio-fixture-r8.json").write_text(json.dumps({"source_before":source,"source_after":after,"source_stable":True,"results":results},indent=2)+"\n",encoding="utf-8")
