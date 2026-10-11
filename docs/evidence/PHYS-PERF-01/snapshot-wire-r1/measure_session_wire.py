"""冻结真实会话快照，仅测传输装配/解析；不作物理吞吐证据。"""
import json
import pickle
import sys
import time
from dataclasses import replace
from pathlib import Path

sys.path.insert(0,str(Path.cwd()/'src'))
from driving_modes import DrivingMode
from session import Session
from session_process import _encode_frame,_decode_frame,_output
from simulation import Control
from vehicle_designs import GR86_DESIGN

results = []
for mode in DrivingMode:
    session = Session(23,track='endless',road_shape='hills',vehicle_config=GR86_DESIGN,driving_mode=mode)
    try:
        session.start(countdown=False)
        session.simulation.step(Control(throttle=.3))
        previous = session.simulation.snapshot()
        session.simulation.step(Control(throttle=.3))
        session.sync_snapshots()
        current = session.current
        output = replace(_output(session),history=(previous,current),previous=previous)
        for kind in ('pickle','native-first','native-repeat'):
            sent, received = {}, {}
            if kind=='native-repeat':
                _decode_frame(_encode_frame(output,sent),received)
            payload = pickle.dumps((True,output,None),protocol=5) if kind=='pickle' else _encode_frame(output,sent)
            times = []
            for _ in range(3):
                started = time.perf_counter()
                for _ in range(500):
                    if kind=='pickle':
                        actual = pickle.loads(pickle.dumps((True,output,None),protocol=5))[1]
                    elif kind=='native-first':
                        actual = _decode_frame(_encode_frame(output))
                    else:
                        actual = _decode_frame(_encode_frame(output,sent),received)
                times.append((time.perf_counter()-started)*1000/500)
            assert actual==output
            results.append({'mode':mode.value,'codec':kind,'payload_bytes':len(payload),'roundtrip_ms':times})
    finally:
        session.close()
Path('logs/performance/snapshot-wire-r1/session-wire-benchmark.json').write_text(json.dumps(results,indent=2),encoding='utf-8')
print(results)
