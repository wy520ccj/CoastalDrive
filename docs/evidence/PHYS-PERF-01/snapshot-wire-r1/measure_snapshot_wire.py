import hashlib
import json
import pickle
import sys
import time
from dataclasses import fields, replace
from pathlib import Path

sys.path.insert(0,str(Path.cwd()/'src'))
from physics_packet_kernels import layout,encode,decode
from simulation import Simulation,Snapshot,Control
from driving_modes import DrivingMode
from vehicle_designs import GR86_DESIGN
from vehicle_state import CarState,WheelState,WheelContactState,WheelDynamicsState
from powertrain import PowertrainState
from suspension import SuspensionState,SuspensionStep
from vehicle_brakes import BrakeState
from vehicle_dynamics import DynamicsState
from vehicle_stability import StabilityState
from vehicle_traction import TractionState
from impact_events import ImpactEvent,ContactState

classes = (Snapshot,CarState,WheelState,WheelContactState,WheelDynamicsState,PowertrainState,
           SuspensionState,SuspensionStep,BrakeState,DynamicsState,StabilityState,TractionState,ImpactEvent,ContactState)
names = tuple(tuple(f.name for f in fields(c)) for c in classes)
schema = layout(classes,names,171)
out = Path('logs/performance/snapshot-wire-r1')
out.mkdir(parents=True,exist_ok=True)
results = []
for mode in DrivingMode:
    sim = Simulation(23,track='endless',road_shape='hills',traffic_count=12,config=mode.configured_vehicle(True,True,True,base_config=GR86_DESIGN),input_config=mode.input_config)
    try:
        sim.step(Control(throttle=.3))
        before = sim.snapshot()
        sim.step(Control(throttle=.3))
        after = sim.snapshot()
        value = (before,after)
        for name,pack,unpack in [('pickle',lambda v:pickle.dumps(v,protocol=5),pickle.loads),
                                 ('native',lambda v:encode(schema,v),lambda v:decode(schema,v))]:
            payload = pack(value)
            assert unpack(payload)==value
            times = []
            for _ in range(3):
                started = time.perf_counter()
                for _ in range(500):
                    unpack(pack(value))
                times.append((time.perf_counter()-started)*1000/500)
            results.append({'mode':mode.value,'codec':name,'bytes':len(payload),'roundtrip_ms':times})
    finally:
        sim.close()
(out/'wire-benchmark.json').write_text(json.dumps(results,indent=2),encoding='utf-8')
print(results)
