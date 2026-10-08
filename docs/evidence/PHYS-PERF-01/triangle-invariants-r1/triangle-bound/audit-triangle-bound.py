"""核对原完整有限三角面查询，保留真实边角回调并记录省去的重复面判断。"""
import json
import subprocess
import sys
import types
from pathlib import Path
root=Path.cwd();folder=root/'logs/physics/PHYS-PERF-01'
sys.path[:0]=[str(root/'src'),str(folder/'contact-system-baseline/b')]
import _contact_system_old as baseline
import triangle_support
import wheel_contact_kernels

old=types.ModuleType('_old_triangle_bound_query');sys.modules[old.__name__]=old
source=subprocess.check_output(['git','show','500ad9b:src/triangle_support.py'],text=True,encoding='utf-8')
exec(source.replace(
    'from wheel_contact_kernels import','from _contact_system_old import'),old.__dict__)
original=wheel_contact_kernels.triangle_support_entry
counts={'queries':0,'hits':0,'old_edge_calls':0,'new_edge_calls':0}

def hexadecimal(value):
    if value is None:return None
    if isinstance(value,float):return value.hex()
    return tuple(hexadecimal(x) for x in value)

def audited(*args):
    def old_edge(*values,**options):
        counts['old_edge_calls']+=1
        return old.triangle_entry(*values,**options)
    def new_edge(*values,**options):
        counts['new_edge_calls']+=1
        return args[-1](*values,**options)
    expected=baseline.triangle_support_entry(*args[:-1],old_edge)
    actual=original(*args[:-1],new_edge)
    assert hexadecimal(actual)==hexadecimal(expected),(counts,args,actual,expected)
    counts['queries']+=1;counts['hits']+=actual is not None
    return actual

triangle_support.triangle_support_entry=audited
import pytest
code=pytest.main(['-q','tests/test_triangle_support.py','tests/test_suspension_candidates.py',
                 'tests/test_cylinder_suspension.py','tests/test_suspension_query_lifetime.py'])
if code==0:
    from simulation import Simulation,Control
    from vehicle_designs import GR86_DESIGN
    from driver_assist import GAME_INPUT
    sim=Simulation(17,track='coastal',traffic_count=8,config=GR86_DESIGN,input_config=GAME_INPUT)
    try:
        for tick in range(24):sim.step(Control(throttle=.3))
    finally:sim.close()
report={'baseline':'ab204a9 independent old full query DLL and original triangle-entry Python + old triangle_face DLL',
        'pytest_code':int(code),'all_output_hex_equal':code==0,'counts':counts}
(folder/'triangle-bound-audit.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
print(json.dumps(report));raise SystemExit(code)
