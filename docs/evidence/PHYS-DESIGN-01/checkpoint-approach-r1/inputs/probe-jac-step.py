"""独立重放中核对悬架修正的试探轮荷同步。"""
import sys
from pathlib import Path
root=Path(__file__).resolve().parents[3];folder=Path(__file__).resolve().parent
sys.path.insert(0,str(root/'src'))
import tire_drivetrain as target
source=(root/'src/tire_drivetrain.py').read_text(encoding='utf-8')
step=float(sys.argv[1]); source=source.replace('plus[j] += .0001','plus[j] += '+repr(step)).replace('minus[j] -= .0001','minus[j] -= '+repr(step)).replace('/ .0002','/ '+repr(2*step))
exec(compile(source,str(root/'src/tire_drivetrain.py')+' load synchronization probe','exec'),target.__dict__)
replay=(folder/'replay-original.py').read_text(encoding='utf-8').replace('replay-original.json','replay-jac-step-1-.json').replace('diagnostic-original.json','diagnostic-jac-step.json')
exec(compile(replay,str(folder/'replay-original.py'),'exec'),{'__file__':str(folder/'replay-original.py')})
