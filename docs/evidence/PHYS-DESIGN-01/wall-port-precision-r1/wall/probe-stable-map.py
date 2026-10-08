"""独立单步比较端口增量补偿重建，原求解器与精度不变。"""
from pathlib import Path
root=Path.cwd();p=root/'logs/physics/PHYS-DESIGN-01-wall/replay-shared.py'
s=p.read_text(encoding='utf-8')
s=s.replace('namespace=dict(tire_drivetrain.__dict__)',
'''sys.path.insert(0,str(folder/'stable-map/b'))
import _stable_map
namespace=dict(tire_drivetrain.__dict__)
namespace['shared_map_state']=_stable_map.shared_map_state''')
s=s.replace("'replay-original.json'","'replay-stable-map.json'")
exec(compile(s,__file__,'exec'))
