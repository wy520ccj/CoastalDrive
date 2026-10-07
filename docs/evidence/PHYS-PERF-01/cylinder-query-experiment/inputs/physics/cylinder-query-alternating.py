"""同进程交替原前置/原生前置；保存四条完整轨迹再检查。"""
import json
import subprocess
import sys
import time
from dataclasses import asdict
from pathlib import Path
root=Path.cwd();sys.path.insert(0,str(root/'src'))
import suspension_contacts as module
import vehicle_suspension
from simulation import Simulation,Control
from vehicle_designs import GR86_DESIGN
from driver_assist import GAME_INPUT
source=subprocess.check_output(['git','show','e5765ed:src/suspension_contacts.py'],text=True,encoding='utf-8')
space=dict(module.__dict__)
begin=source.index('def cylinder_suspension_rays(');end=source.index('def static_support_shapes(',begin)
exec(compile(source[begin:end],'e5765ed original cylinder query','exec'),space)
old=space['cylinder_suspension_rays'];new=module.cylinder_suspension_rays
rows=[]
for kind,function in (('old',old),('new',new),('new',new),('old',old)):
    module.cylinder_suspension_rays=function;vehicle_suspension.cylinder_suspension_rays=function
    sim=Simulation(17,track='coastal',traffic_count=8,config=GR86_DESIGN,input_config=GAME_INPUT)
    started=time.perf_counter();cpu=time.process_time();snapshots=[]
    try:
        for tick in range(48):
            sim.step(Control(throttle=.3,steering=.02 if tick>=24 else 0.))
            state=asdict(sim.snapshot());state['contact_epoch']=0;state['player']['contact_epoch']=0
            for car in state['traffic']:car['contact_epoch']=0
            snapshots.append(state)
        rows.append({'kind':kind,'wall_seconds':time.perf_counter()-started,'cpu_seconds':time.process_time()-cpu,'snapshots':snapshots})
    finally:sim.close()
path=root/'logs/physics/PHYS-PERF-01/cylinder-query-alternating.json'
path.write_text(json.dumps({'scope':'48 ticks9 cars,ABBA short diagnostic; all process-global epoch identities normalized','cases':rows}),encoding='utf-8')
saved=json.loads(path.read_text(encoding='utf-8'))['cases']
assert all(row['snapshots']==saved[0]['snapshots'] for row in saved)
print(json.dumps({'all_four_full_trajectories_equal':True,'cases':[{k:v for k,v in row.items() if k!='snapshots'} for row in rows]}))
