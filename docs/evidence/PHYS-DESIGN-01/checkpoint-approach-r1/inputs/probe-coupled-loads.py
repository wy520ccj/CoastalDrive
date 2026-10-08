"""独立重放中核对悬架修正的试探轮荷同步。"""
import sys
from pathlib import Path
root=Path(__file__).resolve().parents[3];folder=Path(__file__).resolve().parent
sys.path.insert(0,str(root/'src'))
import tire_drivetrain as target
source=(root/'src/tire_drivetrain.py').read_text(encoding='utf-8')
source=source.replace('normal_forces = shared_suspension(suspension, values[:3], values[3:], dt).axial_force\n',
    'normal_forces = shared_suspension(suspension, values[:3], values[3:], dt).axial_force\n            normal_loads()\n')
source=source.replace('suspension, normal_forces = original_system, original_forces\n        normal_projection()',
    'suspension, normal_forces = original_system, original_forces\n        normal_loads()\n        normal_projection()')
exec(compile(source,str(root/'src/tire_drivetrain.py')+' load synchronization probe','exec'),target.__dict__)
replay=(folder/'replay-original.py').read_text(encoding='utf-8').replace('replay-original.json','replay-coupled-loads.json').replace('diagnostic-original.json','diagnostic-coupled-loads.json')
exec(compile(replay,str(folder/'replay-original.py'),'exec'),{'__file__':str(folder/'replay-original.py')})
