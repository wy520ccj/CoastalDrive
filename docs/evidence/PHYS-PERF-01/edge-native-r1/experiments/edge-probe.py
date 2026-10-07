import hashlib
import json
import random
import sys
from pathlib import Path

root = Path(__file__).resolve().parents[3]
folder = Path(__file__).resolve().parent
sys.path[:0] = [str(root/'src'), str(folder/'support-lib')]
import _support_probe
import wheel_envelope

randomizer = random.Random(17)
counts = {'point':0,'edge':0}
for crown in (0., .003):
    for _ in range(512):
        center,axis,a,b = (tuple(randomizer.uniform(-2,2) for _ in range(3)) for _ in range(4))
        for name, function, reference, args in (
            ('point',_support_probe.cylinder_point_delta,wheel_envelope._cylinder_point_delta,(center,axis,.32,.0925,crown)),
            ('edge',_support_probe.cylinder_edge_distance,wheel_envelope._cylinder_edge_distance,(center,axis,a,b,.32,.0925,crown))):
            before,after = reference(*args),function(*args)
            assert before == after, (name,args,before,after)
            counts[name] += 1
report = {'passed':True,'exact_calls':counts,'in_memory_only':True,
          'c_sha256':hashlib.sha256((folder/'support-kernel.c').read_bytes()).hexdigest()}
(folder/'edge-probe-exact.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
print(json.dumps(report))
