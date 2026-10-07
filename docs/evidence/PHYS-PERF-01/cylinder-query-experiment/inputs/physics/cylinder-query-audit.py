"""逐次核对原射线前置值和输入别名；实际世界查询仍运行原入口。"""
import json
import random
import subprocess
import sys
from pathlib import Path
root=Path.cwd();sys.path.insert(0,str(root/'src'))
import suspension_contacts as target
import pytest
source=subprocess.check_output(['git','show','409c03c:src/suspension_contacts.py'],text=True,encoding='utf-8')
begin=source.index('    relative_rays = (rays if ray_origin is not None else')
end=source.index('    cached = candidate_cache',begin)
space={}
body='def original(rays, origin, radius, width, relative):\n    ray_origin = origin if relative else None\n'+source[begin:end]+'    return relative_rays, world_rays, low, high\n'
exec(compile(body,'409c03c original ray prefix','exec'),space)
native=target.cylinder_query_frame
counts={'calls':0,'relative':0,'world':0,'rays':0}
def audited(rays,origin,radius,width,relative):
    old=space['original'](rays,origin,radius,width,relative)
    new=native(rays,origin,radius,width,relative)
    assert new==old,(rays,origin,radius,width,relative,new,old)
    assert new[0 if relative else 1] is rays
    counts['calls']+=1;counts['relative' if relative else 'world']+=1;counts['rays']+=len(rays)
    return new
target.cylinder_query_frame=audited
rng=random.Random(17)
for case in range(64):
    origin=tuple(rng.uniform(-10000,10000) for _ in range(3))
    rays=tuple(tuple(tuple(rng.uniform(-2,2) for _ in range(3)) for _ in range(2)) for _ in range(1+case%4))
    if case%2:rays=list(rays)
    for relative in (False,True):audited(rays,origin,.33,.205,relative)
result=pytest.main(['-q','tests/test_suspension_candidates.py','tests/test_suspension_query_lifetime.py','tests/test_cylinder_suspension.py','tests/test_suspension_contacts.py'])
if result:raise SystemExit(result)
from simulation import Control,Simulation
from vehicle_designs import GR86_DESIGN
from driving_modes import DrivingMode
sim=Simulation(track='coastal',traffic_count=8,seed=17,config=GR86_DESIGN,input_config=DrivingMode.GAME.input_config)
try:
    for _ in range(24):sim.step(Control(throttle=.3))
finally:sim.close()
report={'baseline':'409c03c original suspension ray prefix','all_fields_and_aliases_equal':True,'counts':counts}
(root/'logs/physics/PHYS-PERF-01/cylinder-query-audit.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
print(json.dumps(report))
