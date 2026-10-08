"""旧Python能量账与独立旧悬架DLL对照完整SuspensionStep，含全部离散功。"""
import json
import subprocess
import sys
import types
from dataclasses import asdict
from pathlib import Path
root=Path.cwd();folder=root/'logs/physics/PHYS-PERF-01'
sys.path[:0]=[str(root/'src'),str(folder/'shared-solution-baseline/b')]
import suspension
old=types.ModuleType('_old_suspension_energy');sys.modules[old.__name__]=old
source=subprocess.check_output(['git','show','da6539c:src/suspension.py'],text=True,encoding='utf-8')
exec(source.replace('from mechanical_kernels import','from _shared_solution_old import'),old.__dict__)
original=suspension.advance_suspension
counts={'steps':0,'zero_mobility':0,'elastic_calls':0}
def hex_tree(value):
    if isinstance(value,float):return value.hex()
    if isinstance(value,dict):return {k:hex_tree(x) for k,x in value.items()}
    return tuple(hex_tree(x) for x in value)
def audited(*args,**kwargs):
    expected=old.advance_suspension(*args,**kwargs)
    actual=original(*args,**kwargs)
    assert hex_tree(asdict(actual))==hex_tree(asdict(expected)),(counts,args,kwargs,asdict(actual),asdict(expected))
    counts['steps']+=1;counts['zero_mobility']+=all(x==0. for row in args[2] for x in row)
    return actual
original_elastic=suspension.elastic_terms
def audited_elastic(*args,**kwargs):
    expected=old.elastic_terms(*args,**kwargs);actual=original_elastic(*args,**kwargs)
    assert hex_tree(actual)==hex_tree(expected),(args,actual,expected)
    counts['elastic_calls']+=1
    return actual
suspension.advance_suspension=audited
suspension.elastic_terms=audited_elastic
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
report={'baseline':'da6539c original Python energy formulas and independent127 old suspension/dot DLL',
        'pytest_code':int(code),'all_suspension_step_hex_equal':code==0,'counts':counts}
(folder/'suspension-energy-audit.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
print(json.dumps(report));raise SystemExit(code)
