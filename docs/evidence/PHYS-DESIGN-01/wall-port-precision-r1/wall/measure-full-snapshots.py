"""保存数值精度修复后的完整轨迹与旧逐值基线差异，不把耗时当FPS。"""
import gzip
import json
import sys
import time
from dataclasses import asdict
from pathlib import Path
root=Path.cwd();sys.path.insert(0,str(root/'src'))
from simulation import Simulation,Control
from vehicle_designs import GR86_DESIGN
from driver_assist import GAME_INPUT
folder=root/'logs/physics/PHYS-DESIGN-01-wall'
baseline=json.loads(gzip.decompress((root/'docs/evidence/PHYS-PERF-01/wheel-derivatives-r1/wheel-derivatives-snapshots.json.gz').read_bytes()))
cases=[]
for traffic in (0,8):
    sim=Simulation(17,track='coastal',traffic_count=traffic,config=GR86_DESIGN,input_config=GAME_INPUT)
    start=time.perf_counter();snapshots=[]
    try:
        for tick in range(48):
            sim.step(Control(throttle=.3,steering=.02 if tick>=24 else 0.))
            state=asdict(sim.snapshot());state['player']['contact_epoch']=0
            for car in state['traffic']:car['contact_epoch']=0
            snapshots.append(state)
        cases.append({'traffic':traffic,'seconds':time.perf_counter()-start,'snapshots':snapshots})
    finally:sim.close()
report={'baseline':'a794af9 complete wheel-derivatives snapshots','cases':cases}
(folder/'snapshots.json').write_text(json.dumps(report),encoding='utf-8')
differences=[]
def compare(old,new,path):
    if isinstance(old,dict):
        assert old.keys()==new.keys(),path
        for key in old:compare(old[key],new[key],f'{path}.{key}')
    elif isinstance(old,(list,tuple)):
        assert len(old)==len(new),path
        for i,(a,b) in enumerate(zip(old,new)):compare(a,b,f'{path}[{i}]')
    elif old!=new:
        differences.append({'path':path,'old':old,'new':new,
            'absolute':abs(old-new) if isinstance(old,(float,int)) and isinstance(new,(float,int)) else None})
for a,b in zip(baseline['cases'],cases):
    assert a['traffic']==b['traffic']
    compare(a['snapshots'],b['snapshots'],f'traffic{b["traffic"]}')
summary={'difference_count':len(differences),'non_numeric':[row for row in differences if row['absolute'] is None],
         'largest_numeric':sorted((row for row in differences if row['absolute'] is not None),key=lambda x:x['absolute'],reverse=True)[:20],
         'cases':[{'traffic':c['traffic'],'seconds':c['seconds']} for c in cases]}
(folder/'snapshot-differences.json').write_text(json.dumps(summary,indent=2),encoding='utf-8')
print(json.dumps(summary))
