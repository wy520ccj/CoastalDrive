"""保存实际检查点碰撞测试的失败子步；不替换算术、几何、控制或碰撞。"""
import hashlib
import inspect
import json
import sys
import time
from dataclasses import asdict,fields
from pathlib import Path
root=Path(__file__).resolve().parents[3];folder=Path(__file__).resolve().parent
sys.path.insert(0,str(root/'src'))
import vehicle_tires
from panda3d.core import Vec3
from simulation import Simulation,Control,forward
from vehicle_parameters import save_vehicle_config
original=vehicle_tires.advance_drivetrain;signature=inspect.signature(original)
before={str(p.relative_to(root)):hashlib.sha256(p.read_bytes()).hexdigest() for p in (root/'src').rglob('*') if p.suffix in ('.py','.c','.pyd')}
sim=Simulation(31);started=time.perf_counter()
def observe(*args,**kwargs):
    try:return original(*args,**kwargs)
    except ArithmeticError as error:
        values=dict(signature.bind(*args,**kwargs).arguments)
        chassis=inspect.currentframe().f_back.f_locals['chassis']
        system=values.pop('suspension')
        save_vehicle_config(folder/'config.json',values.pop('config'))
        save_vehicle_config(folder/'rear-config.json',values.pop('rear_config'))
        values['frames']=[asdict(frame) for frame in values['frames']]
        planes=[]
        for plane in system.kinematics:
            if plane is None:planes.append(None);continue
            surface=plane.surface
            planes.append({'hub':plane.hub,'direction':plane.direction,'normal':plane.normal,'length':plane.length,'point':plane.point,
                'surface':{f.name:getattr(surface,f.name) for f in fields(surface) if f.name not in ('world','chassis','envelope','static_shapes','queries','candidates')}})
        record={'error':str(error),'completed_tick':sim.snapshot().tick,'seed':sim.seed,'track':'coastal',
            'arguments':values,'suspension':{f.name:getattr(system,f.name) for f in fields(system) if f.name not in ('config','kinematics')},
            'planes':planes,'solver_chassis':{'name':chassis.getName(),'position':tuple(chassis.getTransform().getPos()),'orientation':tuple(chassis.getTransform().getQuat())},
            'snapshot':asdict(sim.snapshot()),'source_hashes':before,'seconds':time.perf_counter()-started,
            'scope':'exact current main test input; observer only catches and saves ArithmeticError'}
        (folder/'input.json').write_text(json.dumps(record,ensure_ascii=False,indent=2),encoding='utf-8')
        print(json.dumps({'error':str(error),'completed_tick':record['completed_tick'],'seconds':record['seconds']}),flush=True)
        raise
vehicle_tires.advance_drivetrain=observe
try:
    from coastal_map import MAP_POINTS
    point=MAP_POINTS[160]
    sim.reset_player((point.x,point.y,point.z+.55),point.heading)
    for _ in range(180):sim.step(Control())
finally:
    sim.close()
    assert all(hashlib.sha256((root/name).read_bytes()).hexdigest()==digest for name,digest in before.items())

