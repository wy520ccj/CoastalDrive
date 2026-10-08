"""完整悬架数值块与主fa全Snapshot逐字段比较。"""
from pathlib import Path
root=Path.cwd();folder=root/'logs/physics/PHYS-PERF-01'
s=(folder/'measure-triangle-bound.py').read_text(encoding='utf-8')
s=s.replace('triangle-bound-snapshots.json','suspension-energy-snapshots.json')
exec(compile(s,__file__,'exec'))
