"""只在本进程试验原方程的联合预条件块，正式源不变。"""
import json
import sys
import time
from dataclasses import asdict
from pathlib import Path
root=Path(__file__).resolve().parents[3];sys.path.insert(0,str(root/'src'))
import tire_drivetrain as target
folder=Path(__file__).resolve().parent
source=(root/'src/tire_drivetrain.py').read_text(encoding='utf-8')
block=(folder/'coupled-correction-body.py').read_text(encoding='utf-8')
source=source.replace('    def correct_suspension(',block+'    def correct_suspension(',1)
marker='        if shaft and maximum >= .001 and sweep >= 8:\n'
source=source.replace(marker,'''        if shaft and suspension is not None and config.tire_compliance and rear_config.tire_compliance and sweep >= 1 and (
                maximum >= .001 or normal_error >= normal_tolerance or geometry_error >= 1e-12):
            correct_coupled(state, end_velocity)
            continue
'''+marker,1)
exec(compile(source,str(root/'src/tire_drivetrain.py')+' joint numeric experiment','exec'),target.__dict__)
import vehicle_tires
vehicle_tires.advance_drivetrain=target.advance_drivetrain
if '--tests' in sys.argv:
    import pytest
    raise SystemExit(pytest.main(['-q','-x','tests/test_joint_suspension.py','tests/test_tire_drivetrain.py','tests/test_drivetrain_jacobian.py']))
from simulation import Simulation,Control
from vehicle_designs import GR86_DESIGN
from driver_assist import GAME_INPUT
rows=[]
for traffic in (0,8):
    sim=Simulation(17,track='coastal',traffic_count=traffic,config=GR86_DESIGN,input_config=GAME_INPUT)
    start=time.perf_counter();snapshots=[]
    try:
        for tick in range(48):
            sim.step(Control(throttle=.3,steering=.02 if tick>=24 else 0.))
            state=asdict(sim.snapshot());state['player']['contact_epoch']=0
            for car in state['traffic']:car['contact_epoch']=0
            snapshots.append(state)
        rows.append({'traffic':traffic,'seconds':time.perf_counter()-start,'snapshots':snapshots})
    finally:sim.close()
(folder/'coupled-correction-snapshots.json').write_text(json.dumps({'kind':'in-process algorithm experiment, production source unchanged','cases':rows}),encoding='utf-8')
print(json.dumps([{'traffic':r['traffic'],'seconds':r['seconds']} for r in rows]))
