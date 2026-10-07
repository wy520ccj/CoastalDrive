"""同进程四条相同九车轨迹比较单个射线装配块，保留完整快照。"""
import importlib.util
import json
import sys
import time
from dataclasses import asdict
from pathlib import Path
root=Path(__file__).resolve().parents[3];folder=Path(__file__).resolve().parent
sys.path.insert(0,str(root/'src'))
import suspension_contacts as target
paths=list((folder/'surface-prefilter-baseline').rglob('_surface_prefilter_old*.pyd'));assert len(paths)==1
spec=importlib.util.spec_from_file_location('_surface_prefilter_old',paths[0]);baseline=importlib.util.module_from_spec(spec);spec.loader.exec_module(baseline)
current=target.surface_ray_hits
from simulation import Simulation,Control
from vehicle_designs import GR86_DESIGN
from driver_assist import GAME_INPUT
rows=[]
for name,function in [('old',baseline.surface_ray_hits),('prefilter',current),('prefilter',current),('old',baseline.surface_ray_hits)]:
    target.surface_ray_hits=function
    sim=Simulation(17,track='coastal',traffic_count=8,config=GR86_DESIGN,input_config=GAME_INPUT)
    snapshots=[];start=time.perf_counter();cpu=time.process_time()
    try:
        for tick in range(48):
            sim.step(Control(throttle=.3,steering=.02 if tick>=24 else 0.))
            state=asdict(sim.snapshot());state['player']['contact_epoch']=0
            for car in state['traffic']:car['contact_epoch']=0
            snapshots.append(state)
        row={'name':name,'wall_seconds':time.perf_counter()-start,'cpu_seconds':time.process_time()-cpu,'snapshots':snapshots}
        rows.append(row);print(json.dumps({k:v for k,v in row.items() if k!='snapshots'}),flush=True)
    finally:sim.close()
assert all(row['snapshots']==rows[0]['snapshots'] for row in rows)
(folder/'surface-prefilter-alternating.json').write_text(json.dumps({'same_process':True,'all_full_snapshots_equal':True,'contact_epoch_normalized_to0':True,'cases':rows}),encoding='utf-8')
