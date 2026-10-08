"""中心差分按双精度舍入/二阶截断平衡选择当前速度尺度。"""
import sys
from pathlib import Path
root=Path(__file__).resolve().parents[3];folder=Path(__file__).resolve().parent
sys.path.insert(0,str(root/'src'))
import tire_drivetrain as target
source=(root/'src/tire_drivetrain.py').read_text(encoding='utf-8')
begin=source.index('    def correct_suspension(');end=source.index('    state = initial',begin)
block=source[begin:end]
block=block.replace('            plus[j] += .0001\n            minus[j] -= .0001',
    '            step = math.ulp(1.) ** (1 / 3) * max(1., abs(values[j]))\n            plus[j] += step\n            minus[j] -= step')
block=block.replace('/ .0002','/ (plus[j] - minus[j])')
source=source[:begin]+block+source[end:]
exec(compile(source,str(root/'src/tire_drivetrain.py')+' scale aware derivative probe','exec'),target.__dict__)
replay=(folder/'replay-original.py').read_text(encoding='utf-8').replace('replay-original.json','replay-scaled-jacobian.json').replace('diagnostic-original.json','diagnostic-scaled-jacobian.json')
exec(compile(replay,str(folder/'replay-original.py'),'exec'),{'__file__':str(folder/'replay-original.py')})
