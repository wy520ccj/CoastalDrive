"""标准单/九车48拍全部快照对照，耗时只作为短诊断。"""
import hashlib
import json
import sys
import time
from dataclasses import asdict
from pathlib import Path
root=Path.cwd();sys.path.insert(0,str(root/'src'))
from simulation import Simulation,Control
from vehicle_designs import GR86_DESIGN
from driver_assist import GAME_INPUT
folder=root/'logs/physics/PHYS-PERF-01'
def hashes():
    return {str(p.relative_to(root)):hashlib.sha256(p.read_bytes()).hexdigest() for a in ('src','tests','tools') for p in (root/a).rglob('*') if p.suffix in ('.py','.c','.pyd','.json')}
before=hashes();cases=[]
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
after=hashes();assert before==after
report={'sources':before,'cases':cases,'source_stable':True}
path=folder/'wheel-derivatives-snapshots.json'
path.write_text(json.dumps(report),encoding='utf-8')
old=json.loads((folder/'contact-system-snapshots.json').read_text(encoding='utf-8'))
for a,b in zip(json.loads(path.read_text(encoding='utf-8'))['cases'],old['cases']):
    assert a['traffic']==b['traffic'] and a['snapshots']==b['snapshots'],a['traffic']
print(json.dumps({'all_fields_equal':True,'cases':[{'traffic':c['traffic'],'seconds':c['seconds']} for c in cases]}))


