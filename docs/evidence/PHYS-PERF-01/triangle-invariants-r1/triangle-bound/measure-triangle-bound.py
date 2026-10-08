"""当前主线补偿精度基线与查询复用版的完整48拍Snapshot比较。"""
from pathlib import Path
root=Path.cwd()
source=(root/'logs/physics/PHYS-PERF-01/tire-constitutive-snapshots.py').read_text(encoding='utf-8')
source=source.replace('import hashlib','import gzip\nimport hashlib')
source=source.replace("'tire-constitutive-snapshots.json'","'triangle-bound-snapshots.json'")
source=source.replace("old=json.loads((folder/'shared-solution-snapshots.json').read_text(encoding='utf-8'))",
    "old=json.loads(gzip.decompress(Path('B:/AI agent/暑期计算机程序设计/CoastalDrive/docs/evidence/PHYS-DESIGN-01/wall-port-precision-r1/wall/snapshots.json.gz').read_bytes()))")
exec(compile(source,__file__,'exec'))
