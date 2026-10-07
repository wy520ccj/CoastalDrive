import json
import subprocess
import sys
import textwrap
from pathlib import Path
root=Path.cwd();sys.path.insert(0,str(root/'src'))
import suspension_contacts as target
source=subprocess.run(['git','show','105d849:src/suspension_contacts.py'],capture_output=True,text=True,encoding='utf-8',check=True).stdout
begin=source.index('        for body, inverse, frame, half, margin, plane, triangles in surfaces:',source.index('def cylinder_suspension_rays('));end=source.index('        results.append(',begin)
body=textwrap.dedent(source[begin:end])
original=target.surface_ray_hits;counts={'rays':0,'surfaces':0,'hits':0,'relative':0,'world':0,'mesh':0,'plane':0,'box':0}
def audited(surfaces,start,end,axis,origin,radius,reach,width,shoulder,crown,surface_class,contact_class,relative):
    space=dict(target.__dict__)
    space.update(surfaces=surfaces,relative_start=start,relative_end=end,axis=axis,origin=origin,
                 radius=radius,width=width,shoulder=shoulder,crown=crown,ray_origin=origin if relative else None,
                 start=(0.,0.,0.),end=(radius+reach,0.,0.),hits=[])
    # reach已经由原Python表达式求得；旧循环每个支持面的同一reach直接复用该值。
    code=body.replace('reach = math.sqrt(sum((end[a] - start[a])**2 for a in range(3))) - radius','reach = prepared_reach')
    space['prepared_reach']=reach
    exec(compile(code,'105d849 original finite support ray loop','exec'),space)
    expected=space['hits']
    actual=original(surfaces,start,end,axis,origin,radius,reach,width,shoulder,crown,surface_class,contact_class,relative)
    assert actual==expected,(actual,expected)
    for a,b in zip(actual,expected):
        assert a.node is b.node and a.surface.triangles is b.surface.triangles
    counts['rays']+=1;counts['surfaces']+=len(surfaces);counts['hits']+=len(actual)
    counts['relative' if relative else 'world']+=1
    for part in surfaces:counts['mesh' if part[6] is not None else ('plane' if part[5] is not None else 'box')]+=1
    return actual
target.surface_ray_hits=audited
import pytest
code=pytest.main(['-q','-x','tests/test_cylinder_suspension.py','tests/test_triangle_support.py','tests/test_ramp_contact_step.py','tests/test_guardrail_suspension.py','tests/test_suspension_contacts.py'])
if code==0:
    from simulation import Simulation,Control
    from vehicle_designs import GR86_DESIGN
    from driver_assist import GAME_INPUT
    sim=Simulation(17,track='coastal',traffic_count=8,config=GR86_DESIGN,input_config=GAME_INPUT)
    try:
        for tick in range(24):sim.step(Control(throttle=.3,steering=.02 if tick>=12 else 0.))
    finally:sim.close()
report={'passed':code==0,'baseline':'105d849 original finite support loop, original reach expression retained in caller','exact_actual_calls':counts}
(root/'logs/physics/PHYS-PERF-01/surface-ray-real-call-audit.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
print(json.dumps(report));raise SystemExit(code)
