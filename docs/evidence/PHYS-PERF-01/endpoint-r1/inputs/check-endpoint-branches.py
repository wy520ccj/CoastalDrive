import json
import random
import subprocess
import sys
import types
from pathlib import Path
root=Path.cwd();sys.path.insert(0,str(root/'src'))
import suspension_kinematics as target
import wheel_envelope
source=subprocess.run(['git','show','155aa87:src/suspension_kinematics.py'],capture_output=True,text=True,encoding='utf-8',check=True).stdout
space=dict(target.__dict__);space['subtract']=wheel_envelope.subtract
begin=source.index('def cylinder_endpoint(');end=source.index('def face_extension_difference(',begin)
exec(compile(source[begin:end],'155aa87 original endpoint branches','exec'),space)
rng=random.Random(17);counts={'cases':0,'none':0,'gradient':0,'no_face_cross_plane':0}
for case in range(256):
    family=case%4;normal=(0.,0.,-1.) if family==1 else ((.6,0.,.8) if family==2 else (0.,0.,1.))
    endpoint=tuple(rng.uniform(-1,1) for _ in range(3))
    found=None if family==0 else (.2,normal,endpoint,None)
    surface=types.SimpleNamespace(wheel_axis=(1.,0.,0.),wheel_radius=.3,reach=.4,width=.22,
                                  shoulder=.01,crown=.005,relative_entry=lambda a,b,c,value=found:value)
    contact=target.SupportPlane((0.,0.,0.),(0.,0.,-1.),(0.,0.,1.),.3,surface,(0.,0.,-.6))
    velocity=tuple(rng.uniform(-2,2) for _ in range(3));angular=tuple(rng.uniform(-1,1) for _ in range(3))
    args=(contact,(.001,0.,0.),(.0005,0.,0.),(0.,0.,-1.),(0.,0.,-1.),(0.,1.,0.),.01,1.,velocity,angular,1/240)
    actual=target.cylinder_endpoint(*args);expected=space['cylinder_endpoint'](*args)
    assert actual==expected,(case,actual,expected)
    counts['cases']+=1;counts['none' if actual is None else 'gradient']+=1
    counts['no_face_cross_plane']+=family in (2,3)
(root/'logs/physics/PHYS-PERF-01/endpoint-branch-probe.json').write_text(json.dumps({'passed':True,**counts}),encoding='utf-8')
print(counts)
