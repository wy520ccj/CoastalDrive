import ast
import json
from pathlib import Path
import sys
import time

root=Path.cwd()
sys.path.insert(0,str(root/'src'))
import suspension_contacts
from driving_modes import DrivingMode
from panda3d.core import BitMask32
from simulation import Simulation
from vehicle_designs import vehicle_design

source=(root/'logs/performance/static-read-r1/baseline/src/suspension_contacts.py').read_text(encoding='utf-8')
node=next(n for n in ast.parse(source).body if isinstance(n,ast.FunctionDef) and n.name=='static_support_shapes')
namespace=dict(vars(suspension_contacts))
exec(compile(ast.Module(body=[node],type_ignores=[]),'frozen-a7b57ea-static-read','exec'),namespace)
old=namespace['static_support_shapes']
sim=Simulation(track='endless',road_shape='hills',traffic_count=12,config=DrivingMode.SIMULATION.configured_vehicle(
    base_config=vehicle_design('gr86-2022-premium-6mt').config),input_config=DrivingMode.SIMULATION.input_config)
try:
    mask=BitMask32.bit(0)
    samples=[]
    groups=[]
    for name,function in [('old',old),('new',suspension_contacts.static_support_shapes),('new',suspension_contacts.static_support_shapes),('old',old)]:
        cache,packets={},{}
        for _ in range(20):
            geometry=function(sim._world,None,mask,cache=cache,packet_cache=packets)
        durations=[]
        for _ in range(300):
            start=time.perf_counter()
            geometry=function(sim._world,None,mask,cache=cache,packet_cache=packets)
            durations.append((time.perf_counter()-start)*1000)
        groups.append(tuple(geometry))
        samples.append({'reader':name,'mean_ms':sum(durations)/len(durations),'bodies':len(geometry)})
    assert all(value==groups[0] for value in groups)
    report={'kind':'fixed real world metadata reader; no world integration or FPS','samples':samples,'geometry_equal':True}
    (root/'logs/performance/static-read-r1/read-benchmark.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
    print(json.dumps(report))
finally:
    sim.close()
