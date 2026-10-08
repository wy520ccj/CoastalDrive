from pathlib import Path
import json
folder=Path(__file__).resolve().parent
d=json.loads((folder/'input.json').read_text(encoding='utf-8'))
print({k:d[k] for k in ('completed_tick','seconds','solver_chassis','error')})
print([(p['normal'],p['point'],p['length']) if p else None for p in d['planes']])
source=(folder.parent/'PHYS-DESIGN-01-highway/replay-original.py').read_text(encoding='utf-8')
source=source.replace('input-native.json','input.json').replace("track='highway'","track='coastal'")
source=source.replace('original Python equations and arithmetic; not a full T2 run','frozen main 33657dc equations and strict native arithmetic; not a full T2 run')
(folder/'replay-original.py').write_text(source,encoding='utf-8')
