"""只在本诊断进程使用同算术C内核，并保存实际失败子步；不改游戏源码或积分条件。"""
import hashlib
import importlib
import inspect
import json
import sys
import time
from dataclasses import asdict, fields
from pathlib import Path

root=Path(__file__).resolve().parents[3]
isolated=Path('C:/Users/15120/.codex/worktrees/gr86-physics/CoastalDrive')
folder=Path(__file__).resolve().parent
sys.path[:0]=[str(root/'src'),str(isolated/'src'),str(isolated/'logs/physics/PHYS-PERF-01/lu-lib')]
import mechanical_kernels
import wheel_contact_kernels
import _lu_probe

for name in ('rotor_dynamics','suspension','shaft_transmission','driveline_inertia','differential','transmission_ports',
             'suspension_kinematics','triangle_support','wheel_envelope','tire_coupling','tire_drivetrain'):
    module=importlib.import_module(name)
    if 'dot' in vars(module): module.dot=mechanical_kernels.dot
    if 'cross' in vars(module): module.cross=mechanical_kernels.cross
import shaft_transmission
shaft_transmission.shaft_brake_state=mechanical_kernels.shaft_brake_state
import driveline_inertia
import differential
driveline_inertia.project_inertia=mechanical_kernels.project_vector
differential.viscous_projection=mechanical_kernels.project_vector
import suspension
import tire_drivetrain
suspension._solve=_lu_probe.solve_lu
tire_drivetrain._solve=_lu_probe.solve_lu
for name in ('wheel_envelope','triangle_support','suspension_kinematics','wheel_geometry'):
    module=importlib.import_module(name)
    module.cylinder_support=wheel_contact_kernels.cylinder_support
import wheel_envelope
wheel_envelope._cylinder_point_delta=wheel_contact_kernels.cylinder_point_delta
wheel_envelope._cylinder_edge_distance=wheel_contact_kernels.cylinder_edge_distance
import triangle_support
source=(root/'src/triangle_support.py').read_text(encoding='utf-8')
first=source.index('    a, b, c = triangle\n')
last=source.index('    if face_only:\n        return None\n',first)+len('    if face_only:\n        return None\n')
source=source[:first]+'''    finished, hit = triangle_face(start,end,triangle,margin,axis,radius,width,shoulder,crown,
                                   face_only=face_only,ceiling=ceiling)
    if finished:
        return hit
    velocity = subtract(end,start)
'''+source[last:]
triangle_support.triangle_face=wheel_contact_kernels.triangle_face
exec(compile(source,str(root/'src/triangle_support.py'),'exec'),triangle_support.__dict__)
triangle_support.dot=mechanical_kernels.dot
triangle_support.cylinder_support=wheel_contact_kernels.cylinder_support

import vehicle_tires
from simulation import Control, Simulation
from vehicle_parameters import save_vehicle_config

before={str(p.relative_to(root)):hashlib.sha256(p.read_bytes()).hexdigest() for p in (root/'src').rglob('*.py')}
original=vehicle_tires.advance_drivetrain
sim=Simulation(track='highway')
started=time.perf_counter()
signature=inspect.signature(original)

def observe(*args,**kwargs):
    try:
        return original(*args,**kwargs)
    except ArithmeticError as error:
        values=dict(signature.bind(*args,**kwargs).arguments)
        chassis=inspect.currentframe().f_back.f_locals['chassis']
        system=values.pop('suspension')
        save_vehicle_config(folder/'config.json',values.pop('config'))
        save_vehicle_config(folder/'rear-config.json',values.pop('rear_config'))
        values['frames']=[asdict(frame) for frame in values['frames']]
        planes=[]
        for plane in system.kinematics:
            if plane is None:
                planes.append(None)
                continue
            surface=plane.surface
            planes.append({'hub':plane.hub,'direction':plane.direction,'normal':plane.normal,'length':plane.length,'point':plane.point,
                'surface':{f.name:getattr(surface,f.name) for f in fields(surface) if f.name not in ('world','chassis','envelope')}})
        record={'error':str(error),'completed_tick':sim.snapshot().tick,'seed':sim.seed,'track':str(sim.track),
            'arguments':values,'suspension':{f.name:getattr(system,f.name) for f in fields(system) if f.name not in ('config','kinematics')},
            'planes':planes,'solver_chassis':{'name':chassis.getName(),'position':tuple(chassis.getTransform().getPos()),
                'orientation':tuple(chassis.getTransform().getQuat())},
            'snapshot':asdict(sim.snapshot()),'source_hashes':before,
            'diagnostic_arithmetic':'Main equations and finite differences; only exact C arithmetic/geometry/LU substituted in this process. No source edits, teleport, collision mask, tolerance or iteration changes.',
            'native_modules':{name:hashlib.sha256(Path(module.__file__).read_bytes()).hexdigest() for name,module in
                (('mechanical_kernels',mechanical_kernels),('wheel_contact_kernels',wheel_contact_kernels),('_lu_probe',_lu_probe))}}
        (folder/'input-native.json').write_text(json.dumps(record,ensure_ascii=False,indent=2),encoding='utf-8')
        print(json.dumps({'error':str(error),'completed_tick':record['completed_tick'],'seconds':time.perf_counter()-started},ensure_ascii=True),flush=True)
        raise

vehicle_tires.advance_drivetrain=observe
try:
    for tick in range(18000):
        sim.step(Control())
        if tick%600 == 0:
            print(json.dumps({'completed_ticks':tick+1,'seconds':time.perf_counter()-started}),flush=True)
finally:
    sim.close()
    assert all(hashlib.sha256((root/name).read_bytes()).hexdigest()==digest for name,digest in before.items())
