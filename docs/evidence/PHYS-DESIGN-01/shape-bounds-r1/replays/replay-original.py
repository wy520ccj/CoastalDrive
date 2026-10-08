"""把保存的一个失败子步放回同一静态道路，以主目录原Python实现独立重放。"""
import hashlib
import json
import sys
from pathlib import Path

from panda3d.core import Quat, TransformState, Vec3

root=Path(__file__).resolve().parents[3]
sys.path[:0]=[str(root/'src'),str(root/'tools')]
from simulation import Simulation
from suspension import SuspensionInput
from suspension_kinematics import SupportPlane
from tire_coupling import ContactFrame
from tire_drivetrain import advance_drivetrain
from vehicle_config import CAR
from vehicle_parameters import load_vehicle_config
from vehicle_suspension import WorldSurface
from wheel_dynamics import Mobility

def tuples(value):
    if isinstance(value,list): return tuple(tuples(v) for v in value)
    if isinstance(value,dict): return {k:tuples(v) for k,v in value.items()}
    return value

folder=Path(__file__).resolve().parent
record=tuples(json.loads((folder/'input-native.json').read_text(encoding='utf-8')))
config=load_vehicle_config(folder/'config.json',CAR)
rear=load_vehicle_config(folder/'rear-config.json',CAR)
before={str(p.relative_to(root)):hashlib.sha256(p.read_bytes()).hexdigest() for p in (root/'src').rglob('*.py')}
sim=Simulation(record['seed'],track='highway')
pose=record['solver_chassis']
sim.player._chassis.setTransform(TransformState.makePosQuatScale(Vec3(*pose['position']),Quat(*pose['orientation']),Vec3(1)))
planes=[]
for values in record['planes']:
    if values is None:
        planes.append(None)
        continue
    surface=WorldSurface(**values.pop('surface'),world=sim._world,chassis=sim.player._chassis,envelope=sim.player.suspension.envelope)
    planes.append(SupportPlane(**values,surface=surface))
system=SuspensionInput(**record['suspension'],config=config,kinematics=tuple(planes))
arguments=record['arguments']
frames=[]
for frame in arguments.pop('frames'):
    frame['mobility']=Mobility(**frame['mobility'])
    frames.append(ContactFrame(**frame))
try:
    result=advance_drivetrain(**arguments,frames=tuple(frames),config=config,rear_config=rear,suspension=system)
    report={'status':'passed','sweeps':result.sweeps,'normal_residual':result.normal_residual,
            'energy_residual_J':result.suspension.energy_residual,'angular':result.angular,'velocity':result.velocity}
except ArithmeticError as error:
    tb=error.__traceback__
    while tb.tb_next is not None: tb=tb.tb_next
    values=tb.tb_frame.f_locals
    diagnostic={name:values[name] for name in ('state','end_velocity','normal_forces','maximum','normal_error','geometry_error','forces','modes')}
    diagnostic['old_gradients']=values['suspension'].gradients
    diagnostic['new_gradients']=values['target_system'].gradients
    diagnostic['touching']=values['target_system'].touching
    (folder/'diagnostic-original.json').write_text(json.dumps(diagnostic,indent=2),encoding='utf-8')
    report={'status':'failed','error':str(error),'matches_captured_error':str(error)==record['error']}
finally:
    sim.close()
    assert all(hashlib.sha256((root/name).read_bytes()).hexdigest()==digest for name,digest in before.items())
report['src_sha256']=before
report['kind']='single saved substep, original Python equations and arithmetic; not a full T2 run'
(folder/'replay-original.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
print(json.dumps({k:v for k,v in report.items() if k!='src_sha256'}))
