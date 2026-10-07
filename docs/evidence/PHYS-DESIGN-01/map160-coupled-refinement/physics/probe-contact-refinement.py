"""几何未收敛时补原接触Newton修正；在独立进程检查保存输入。"""
import sys
from pathlib import Path
root=Path(__file__).resolve().parents[3];folder=Path(__file__).resolve().parent
sys.path.insert(0,str(root/'src'))
import tire_drivetrain as target
source=(root/'src/tire_drivetrain.py').read_text(encoding='utf-8')
old='        if shaft and maximum >= .001 and sweep >= 8:'
new='        if shaft and sweep >= 8 and (maximum >= .001 or geometry_error >= 1e-12):'
assert source.count(old)==1
exec(compile(source.replace(old,new),str(root/'src/tire_drivetrain.py')+' contact refinement probe','exec'),target.__dict__)
replay=(folder/'replay-original.py').read_text(encoding='utf-8').replace('replay-original.json','replay-refinement-probe.json').replace('diagnostic-original.json','diagnostic-refinement-probe.json')
exec(compile(replay,str(folder/'replay-original.py')+' contact refinement probe','exec'),{'__file__':str(folder/'replay-original.py'),'__name__':'contact_refinement_probe'})
