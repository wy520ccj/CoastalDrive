from pathlib import Path
import sys,json,gzip,math
from dataclasses import asdict
root=Path.cwd();sys.path[:0]=[str(root/'src'),str(root/'tools')]
from session import Session,Phase
from race import GameMode,BestTimes
from workshop import build_config
from lab_records import model_fingerprint
from lab_runtime import runtime_fingerprint
out=root/'logs/validation/BRAKE-ROAD-01-probe';out.mkdir()
summary={'source_start':model_fingerprint(),'runtime_start':runtime_fingerprint(),'cases':[]}
try:
 for index in range(4):
  s=Session(scores=BestTimes(out/f'{index}-best.json'),vehicle_config=build_config(index,False))
  try:
   s.start(mode=GameMode.BRAKING_LESSON,track='endless',seed=0,settle_initial=True)
   for _ in range(360):s.tick()
   assert s.phase==Phase.DRIVING
   rows=[];braking=False
   for _ in range(3602):
    result=s.highway.snapshot.braking;state=s.current
    if result.position>=100.:braking=True
    desired=('s' if state.player.speed>.3 else '') if braking else ('w' if state.player.speed<82.5/3.6 else '')
    for key in ('w','s'):
     s.keyboard.press(key) if key==desired else s.keyboard.release(key)
    s.tick();result=s.highway.snapshot.braking;state=s.current
    rows.append({'tick':state.tick,'time':state.time,'position':state.player.position,'velocity':state.player.velocity,'heading':state.player.heading,'collisions':state.collisions,'request':asdict(s.last_control),'keys':sorted(s.keyboard.pressed),'result':asdict(result)})
    if result.finished:break
   case={'index':index,'config':asdict(s.vehicle_config),'rows':len(rows),'result':asdict(result),'from_gate_m':result.position-100.}
   with gzip.open(out/f'{index}-raw.json.gz','wt',encoding='utf-8') as f:json.dump(rows,f)
   summary['cases'].append(case);print(json.dumps({k:v for k,v in case.items() if k!='config'},ensure_ascii=False),flush=True)
  finally:s.close()
finally:
 summary.update(source_end=model_fingerprint(),runtime_end=runtime_fingerprint())
 (out/'summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding='utf-8')
