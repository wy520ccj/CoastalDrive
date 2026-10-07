"""在收敛判据原位置观察共同迭代，不改数值或判断。"""
import json
import sys
from pathlib import Path
root=Path(__file__).resolve().parents[3];folder=Path(__file__).resolve().parent
sys.path.insert(0,str(root/'src'))
import tire_drivetrain as target
rows=[]
def observe(sweep,state,velocity,forces,maximum,normal_error,geometry_error,old,new,dt):
    rows.append({'sweep':sweep,'state':state,'velocity':velocity,'normal_forces':forces,
                 'maximum':maximum,'normal_error':normal_error,'geometry_error':geometry_error,
                 'old':old.gradients,'new':new.gradients,'dt':dt})
target.observe=observe
source=(root/'src/tire_drivetrain.py').read_text(encoding='utf-8')
marker='        if maximum < .001 and brake_error < 1e-9 and normal_error < normal_tolerance and geometry_error < 1e-12:'
assert source.count(marker)==1
source=source.replace(marker,'        observe(sweep,state,end_velocity,normal_forces,maximum,normal_error,geometry_error,suspension,target_system,dt)\n'+marker)
exec(compile(source,str(root/'src/tire_drivetrain.py')+' observation only','exec'),target.__dict__)
exec(compile((folder/'replay-original.py').read_text(encoding='utf-8'),str(folder/'replay-original.py'),'exec'),{'__file__':str(folder/'replay-original.py'),'__name__':'observed_replay'})
(folder/'iteration-observations.json').write_text(json.dumps(rows,indent=2),encoding='utf-8')
print(json.dumps([{'sweep':r['sweep'],'geometry':r['geometry_error'],'force_error':r['maximum']} for r in rows],indent=2))
