"""只在独立重放进程比较舍入方案，不修改正式源码或残差门槛。"""
import sys
from pathlib import Path
root=Path(__file__).resolve().parents[3];sys.path.insert(0,str(root/'src'))
import suspension_kinematics as target
source=(root/'src/suspension_kinematics.py').read_text(encoding='utf-8')
mode=sys.argv[1]
if mode=='correction':
    source=source.replace('(difference / dt - sum(g * v for g, v in zip(gradient, speed))) / squared',
        'math.fsum((difference / dt, *(-g * v for g, v in zip(gradient, speed)))) / squared')
    source=source.replace('tuple(g + correction * v for g, v in zip(gradient, speed))',
        'tuple(math.fma(correction, v, g) for g, v in zip(gradient, speed))')
elif mode=='transport':
    source=source.replace('dt * velocity[a] + hub_end[a] - contact.hub[a]',
        'math.fsum((dt * velocity[a], hub_end[a], -contact.hub[a]))')
    source=source.replace('clearance, dt * dot(normal, transport)',
        'clearance, *(dt * normal[a] * transport[a] for a in range(3))')
elif mode=='clearance':
    source=source.replace('*(normal[a] * (contact.hub[a] - anchor[a]) for a in range(3))',
        '*(normal[a] * contact.hub[a] for a in range(3)), *(-normal[a] * anchor[a] for a in range(3))')
elif mode=='same-plane':
    source=source.replace('p0 + dot(normal, tuple(dt * velocity[a] + hub_end[a] - contact.hub[a] for a in range(3))) - extent_secant * axis_change',
        'math.fsum((p0, *(normal[a] * dt * velocity[a] for a in range(3)), *(normal[a] * (hub_end[a] - contact.hub[a]) for a in range(3)), -extent_secant * axis_change))')
else:raise ValueError(mode)
exec(compile(source,str(root/'src/suspension_kinematics.py')+' numeric probe '+mode,'exec'),target.__dict__)
folder=Path(__file__).resolve().parent
replay=(folder/'replay-original.py').read_text(encoding='utf-8').replace('replay-original.json','replay-'+mode+'.json').replace('diagnostic-original.json','diagnostic-'+mode+'.json')
exec(compile(replay,str(folder/'replay-original.py'),'exec'),{'__file__':str(folder/'replay-original.py')})
