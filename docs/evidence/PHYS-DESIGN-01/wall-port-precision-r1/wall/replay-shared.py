"""独立重建失败共同数值系统，观测原30轮的逐坐标残差。"""
import json
import math
import subprocess
import sys
import textwrap
from pathlib import Path
from types import SimpleNamespace

root=Path.cwd();sys.path.insert(0,str(root/'src'))
folder=root/'logs/physics/PHYS-DESIGN-01-wall'
import mechanical_kernels
import tire_drivetrain

def unpack(value):
    if isinstance(value,dict):
        if 'capsule' in value:
            return getattr(mechanical_kernels,value['capsule'])(*unpack(value['args']),**unpack(value['kwargs']))
        if 'tuple' in value:return tuple(unpack(x) for x in value['tuple'])
        return {k:unpack(v) for k,v in value.items()}
    if isinstance(value,list):return [unpack(x) for x in value]
    return value

packet=unpack(json.loads((folder/'shared-input.json').read_text(encoding='utf-8')))
assert packet['shaft'] and not packet['torque_bias']
history=[]
def observe(iteration,state,end):
    residual=tuple(a-b for a,b in zip(state,end))
    history.append({'iteration':iteration,'state':state,'target':end,'residual':residual,
                    'failing_coordinates':[i for i,(a,b) in enumerate(zip(state,end))
                        if abs(a-b)>max(1e-14,math.ulp(a),math.ulp(b))]})

source=subprocess.check_output(['git','show','37cb7f7:src/tire_drivetrain.py'],text=True,encoding='utf-8')
start=source.index('    def shared_jacobian_columns(state):')
end=source.index('\n    def velocities(index, state, end_velocity):',start)
body=textwrap.dedent(source[start:end]).replace('nonlocal ','global ')
body=body.replace('        if angular_converged and ports_converged:',
                  '        observe(iteration,state,end)\n        if angular_converged and ports_converged:')
tire_drivetrain.shared_map_state=mechanical_kernels.shared_map_state
tire_drivetrain.shared_map_jacobian=mechanical_kernels.shared_map_jacobian
namespace=dict(tire_drivetrain.__dict__)
namespace.update(packet)
namespace.update(load_terms=lambda:packet['loads'], road_torques=(0.,)*4, active_limits=(0.,)*3,
                 frames=tuple(SimpleNamespace(load=load,supported=support) for load,support in zip(packet['wheel_loads'],packet['supported'])),
                 observe=observe)
exec(compile(body,'original shared control','exec'),namespace)
try:
    result=namespace['shared'](packet['guess'])
except ArithmeticError as error:
    report={'status':'failed','exception':str(error),'history':history}
    assert history[-1]['residual']==packet['residual'],(history[-1],packet['residual'])
    report['saved_residual_exact']=True
else:
    report={'status':'passed','result':result,'history':history}
(folder/'replay-original.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
print(json.dumps({k:v for k,v in report.items() if k!='history'}))
for row in history:
    print(row['iteration'], row['failing_coordinates'], max(map(abs,row['residual'])),
          [row['residual'][i] for i in row['failing_coordinates']])
