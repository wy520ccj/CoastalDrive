"""冻结原Python轮胎本构；逐值核对分区、变形、滑移、目标及解析导数。"""
import json
import random
import subprocess
import sys
from pathlib import Path
root=Path.cwd();folder=root/'logs/physics/PHYS-PERF-01';sys.path.insert(0,str(root/'src'))
import tire_compliance as compliance
import tire_forces as forces
import pytest
def frozen(name):
    namespace={'__name__':name+'_original'}
    source=subprocess.check_output(['git','show','12ea82b:src/'+name+'.py'],text=True,encoding='utf-8')
    exec(compile(source,'12ea82b original '+name,'exec'),namespace)
    return namespace
old_force=frozen('tire_forces');old_compliance=frozen('tire_compliance')
old_compliance['combined_force']=old_force['combined_force']
counts={'combined':0,'contact':0,'jacobian':0,'rolling':0,'sticking':0,'sliding':0}
def wrap(name,native,original):
    def audited(*args,**kwargs):
        old=original(*args,**kwargs);new=native(*args,**kwargs)
        assert old==new,(name,counts,args,old,new)
        counts[name]+=1
        if name=='contact':counts[new[-1].removeprefix('compliant-')]+=1
        return new
    return audited
forces.combined_force=wrap('combined',forces.combined_force,old_force['combined_force'])
compliance.contact_force=wrap('contact',compliance.contact_force,old_compliance['contact_force'])
compliance.contact_jacobian=wrap('jacobian',compliance.contact_jacobian,old_compliance['contact_jacobian'])
rng=random.Random(17)
for case in range(256):
    force=tuple(rng.uniform(-6000,6000) for _ in range(2))
    previous=tuple(rng.uniform(-.03,.03) for _ in range(2))
    slip=tuple(rng.uniform(-2,2) for _ in range(2))
    jacobian=tuple(tuple(rng.uniform(-.01,.01) for _ in range(2)) for _ in range(2))
    denominator=rng.uniform(.5,20);grip=0. if case%8==0 else rng.uniform(100,8000)
    args=(force,previous,slip,denominator,bool(case%2),grip,80000.,70000.,1/240,300000.,2000.,1.3,.97)
    compliance.contact_force(*args)
    compliance.contact_jacobian(force,previous,slip,jacobian,denominator,(.001,-.002),*args[4:])
    forces.combined_force(slip[0],slip[1],grip,80000.,70000.,1.3,.97)
result=pytest.main(['-q','-x','tests/test_tire_drivetrain.py','tests/test_tire_shaft.py','tests/test_joint_suspension.py'])
if result:raise SystemExit(result)
from simulation import Simulation,Control
from vehicle_designs import GR86_DESIGN
from driving_modes import DrivingMode
sim=Simulation(17,track='coastal',traffic_count=8,config=GR86_DESIGN,input_config=DrivingMode.GAME.input_config)
try:
    for _ in range(24):sim.step(Control(throttle=.3))
finally:sim.close()
report={'baseline':'12ea82b original Python combined/compliant force and Jacobian; originalmath.hypot preserved','all_values_equal':True,'counts':counts}
(folder/'tire-constitutive-audit.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
print(json.dumps(report))
