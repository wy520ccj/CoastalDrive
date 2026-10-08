"""同配置完整48拍快照逐字段对照；耗时只用于候选诊断。"""
from pathlib import Path
root=Path.cwd()
source=(root/'logs/physics/PHYS-PERF-01/tire-constitutive-snapshots.py').read_text(encoding='utf-8')
source=source.replace("'tire-constitutive-snapshots.json'","'contact-system-snapshots.json'")
source=source.replace("'shared-solution-snapshots.json'","'tire-constitutive-snapshots.json'")
exec(compile(source,__file__,'exec'))
