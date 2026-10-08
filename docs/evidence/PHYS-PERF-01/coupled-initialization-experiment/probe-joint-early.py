"""独立进程试验提前执行原联立Newton；方程、上限与所有接受精度保持。"""
from pathlib import Path
root=Path.cwd();folder=root/'logs/physics/PHYS-PERF-01'
s=(folder/'probe-normal-warm.py').read_text(encoding='utf-8')
start=s.index("old='    normal_forces = (0.,) * 4'")
end=s.index('exec(compile(source,',start)
s=s[:start]+'''assert source.count('sweep >= 8')==2
source=source.replace('sweep >= 8','sweep >= 3')
(folder/'joint-early-trial-source.py').write_text(source,encoding='utf-8')
'''+s[end:]
s=s.replace('normal warm process-only trial','early joint Newton process-only trial')
s=s.replace('normal-warm-snapshots','joint-early-snapshots').replace('normal-warm-trial.json','joint-early-trial.json')
exec(compile(s,__file__,'exec'))
