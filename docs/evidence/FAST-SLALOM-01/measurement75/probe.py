from pathlib import Path
import sys,json,gzip
from dataclasses import asdict
root=Path.cwd();sys.path[:0]=[str(root/'src'),str(root/'tools')]
from session import Session,Phase
from race import GameMode,BestTimes
from workshop_cornering import build_config
from slalom_driver import SlalomDriver,apply_keys
from lab_records import model_fingerprint
from lab_runtime import runtime_fingerprint

output=root/'logs/validation/MOD-ROAD-01-probe75';output.mkdir(exist_ok=False)
summary={'source_start':model_fingerprint(),'runtime_start':runtime_fingerprint(),'cases':[]}
try:
 for index in range(4):
  s=Session(scores=BestTimes(output/f'{index}-best.json'),vehicle_config=build_config(index,False,False))
  try:
   s.start(mode=GameMode.SLALOM_LESSON,track='endless',seed=0,settle_initial=True)
   for _ in range(360):s.tick()
   assert s.phase==Phase.DRIVING
   driver=SlalomDriver(75,s.vehicle_config,origin=s.current.player.position[1]);rows=[]
   for _ in range(4802):
    apply_keys(s.keyboard,driver.sample(s.current,1/120));s.tick()
    state=s.current;result=s.highway.snapshot.slalom
    rows.append({'tick':state.tick,'time':state.time,'position':state.player.position,'velocity':state.player.velocity,'heading':state.player.heading,'collisions':state.collisions,'request':asdict(s.last_control),'result':asdict(result)})
    if s.phase==Phase.RESULTS:break
   with gzip.open(output/f'{index}-raw.json.gz','wt',encoding='utf-8') as f:json.dump(rows,f)
   case={'tire_index':index,'config':asdict(s.vehicle_config),'rows':len(rows),'result':asdict(result)};summary['cases'].append(case)
   print(json.dumps({'tire_index':index,'rows':len(rows),'result':asdict(result)},ensure_ascii=False),flush=True)
  finally:s.close()
finally:
 summary.update(source_end=model_fingerprint(),runtime_end=runtime_fingerprint())
 (output/'summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding='utf-8')

