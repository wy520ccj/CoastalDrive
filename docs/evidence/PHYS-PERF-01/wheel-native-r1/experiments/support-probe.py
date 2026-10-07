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
inputs = []
for crown in (0., .003):
    for direction in ((0.,0.,0.),(1.,0.,0.),(1.,1e-14,0.),(0.,0.,1.),(-1.,0.,0.)):
        inputs.append((direction,(1.,0.,0.),.33,.1025,.01,crown))
    for _ in range(1024):
        direction, axis = (tuple(randomizer.uniform(-2,2) for _ in range(3)) for _ in range(2))
        inputs.append((direction,axis,.33,.1025,.01,crown))
for index, args in enumerate(inputs):
    before = wheel_envelope.cylinder_support(*args)
    after = _support_probe.cylinder_support(*args)
    if before != after:
        report = {'passed': False, 'index':index,'input':args,'before':before,'after':after}
        (folder/'support-probe-exact.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
        raise AssertionError(report)
report = {'passed':True,'exact_calls':len(inputs),'in_memory_only':True,
          'c_sha256':hashlib.sha256((folder/'support-kernel.c').read_bytes()).hexdigest()}
(folder/'support-probe-exact.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
print(json.dumps(report))
