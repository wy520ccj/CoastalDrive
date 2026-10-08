"""与独立旧原生悬架核对完整字段，覆盖闭式受压分区与原一般活动集。"""
import json
import sys
from pathlib import Path
root=Path.cwd();folder=root/'logs/physics/PHYS-PERF-01'
sys.path[:0]=[str(root/'src'),str(folder/'shared-solution-baseline/b')]
import _shared_solution_old as baseline
import mechanical_kernels
import suspension
native=mechanical_kernels.suspension_contact_state
counts={'calls':0,'zero_mobility':0,'prescribed_four_contact':0,'general_partition':0}

def hex_tree(value):
    if isinstance(value,float):return value.hex()
    return tuple(hex_tree(x) for x in value)

def audited(*args):
    expected=baseline.suspension_contact_state(*args)
    actual=native(*args)
    assert hex_tree(actual)==hex_tree(expected),(counts,args,actual,expected)
    counts['calls']+=1
    zero=all(x==0. for row in args[2] for x in row)
    counts['zero_mobility']+=zero
    direct=zero and all(args[3]) and all(x>=0. for x in actual[2])
    counts['prescribed_four_contact' if direct else 'general_partition']+=1
    return actual

suspension.suspension_contact_state=audited
mechanical_kernels.suspension_contact_state=audited
import pytest
code=pytest.main(['-q','tests/test_suspension_si.py','tests/test_suspension_coupling.py',
    'tests/test_suspension_native.py','tests/test_joint_suspension.py','tests/test_finite_suspension.py',
    'tests/test_curved_suspension.py','tests/test_guardrail_suspension.py','tests/test_tire_shaft.py'])
if code==0:
    from simulation import Simulation,Control
    from vehicle_designs import GR86_DESIGN
    from driver_assist import GAME_INPUT
    sim=Simulation(17,track='coastal',traffic_count=8,config=GR86_DESIGN,input_config=GAME_INPUT)
    try:
        for tick in range(24):sim.step(Control(throttle=.3))
    finally:sim.close()
report={'baseline':'127c1d0 independent _shared_solution_old native original suspension active set',
        'pytest_code':int(code),'all_output_hex_equal':code==0,'counts':counts}
(folder/'suspension-prescribed-audit.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
print(json.dumps(report));raise SystemExit(code)
