"""每个实际活动集调用均与冻结原实现对照，比较全部机械与能量字段。"""
import dataclasses
import json
import subprocess
import sys
import types
from pathlib import Path
root=Path.cwd()
sys.path.insert(0,str(root/'src'))
import suspension
import pytest
baseline=types.ModuleType('suspension_state_baseline')
sys.modules[baseline.__name__]=baseline
source=subprocess.check_output(['git','show','d3859f8:src/suspension.py'],text=True,encoding='utf-8')
exec(compile(source,'d3859f8 original suspension','exec'),baseline.__dict__)
actual=suspension.advance_suspension
counts={'calls':0,'zero_mobility':0,'nonzero_mobility':0,'free_wheels':0,'stop_input':0}
def audited(*args,**kwargs):
    old=baseline.advance_suspension(*args,**kwargs)
    new=actual(*args,**kwargs)
    assert dataclasses.asdict(old)==dataclasses.asdict(new), (counts,dataclasses.asdict(old),dataclasses.asdict(new))
    counts['calls']+=1
    counts['zero_mobility' if all(v==0. for row in args[2] for v in row) else 'nonzero_mobility']+=1
    counts['free_wheels']+=int(not all(args[3]))
    counts['stop_input']+=int(any(abs(x)>args[9] for x in args[0]))
    return new
suspension.advance_suspension=audited
result=pytest.main(['-q','tests/test_suspension_coupling.py','tests/test_joint_suspension.py','tests/test_finite_suspension.py'])
if result:raise SystemExit(result)
from simulation import Control,Simulation
from vehicle_designs import GR86_DESIGN
from driving_modes import DrivingMode
simulation=Simulation(track='coastal',traffic_count=8,seed=17,config=GR86_DESIGN,input_config=DrivingMode.GAME.input_config)
try:
    for _ in range(24):simulation.step(Control(throttle=.3))
finally:simulation.close()
report={'baseline':'d3859f8 original suspension active set and energy account','all_fields_equal':True,'counts':counts}
(root/'logs/physics/PHYS-PERF-01/suspension-state-audit.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
print(json.dumps(report))
