import json,subprocess,sys,types
from pathlib import Path
root=Path.cwd();sys.path.insert(0,str(root/'src'))
import triangle_support as current
old=types.ModuleType('triangle_query_baseline');sys.modules[old.__name__]=old
source=subprocess.run(['git','show','f44aeb1:src/triangle_support.py'],capture_output=True,text=True,encoding='utf-8',check=True).stdout
exec(compile(source,'f44aeb1 triangle support','exec'),old.__dict__)
original=current.triangle_support_entry;count=0;hits=0

def audited(node,start,end,margin,axis,radius,width,shoulder,crown,edge_entry):
 global count,hits
 actual=original(node,start,end,margin,axis,radius,width,shoulder,crown,edge_entry)
 expected=old.TriangleSupport.entry(node,start,end,margin,axis,radius,width,shoulder,crown)
 assert actual==expected,(actual,expected,(start,end,axis,radius,width,shoulder,crown))
 count+=1;hits+=actual is not None
 return actual
current.triangle_support_entry=audited
import pytest
code=pytest.main(['-q','-x','tests/test_triangle_support.py','tests/test_ramp_contact_step.py','tests/test_guardrail_suspension.py'])
if code==0:
 from simulation import Simulation,Control
 from vehicle_designs import GR86_DESIGN
 from driver_assist import GAME_INPUT
 sim=Simulation(17,track='coastal',traffic_count=8,config=GR86_DESIGN,input_config=GAME_INPUT)
 try:
  for tick in range(24):sim.step(Control(throttle=.3,steering=.02 if tick>=12 else 0.))
 finally:sim.close()
report={'passed':code==0,'exact_real_queries':count,'hit_queries':hits,'reference':'f44aeb1 original TriangleSupport.entry with original candidate generator/edge solver','comparison_instrumentation_only_in_this_process':True}
(root/'logs/physics/PHYS-PERF-01/triangle-query-real-call-audit.json').write_text(json.dumps(report,indent=2),encoding='utf-8');print(json.dumps(report));raise SystemExit(code)
