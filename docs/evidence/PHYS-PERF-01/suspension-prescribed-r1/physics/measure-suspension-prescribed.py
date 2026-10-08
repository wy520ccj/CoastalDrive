"""完整48拍对照原精度主线，耗时仅作为闭式分区候选诊断。"""
from pathlib import Path
root=Path.cwd();folder=root/'logs/physics/PHYS-PERF-01'
s=(folder/'measure-triangle-bound.py').read_text(encoding='utf-8')
s=s.replace('triangle-bound-snapshots.json','suspension-prescribed-snapshots.json')
exec(compile(s,__file__,'exec'))
