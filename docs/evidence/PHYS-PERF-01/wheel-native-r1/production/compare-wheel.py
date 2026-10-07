import hashlib
import json
from pathlib import Path

root = Path(__file__).resolve().parents[3]
folder = Path(__file__).resolve().parent
after = json.loads((folder/'wheel-production-snapshots.json').read_text(encoding='utf-8'))
comparisons = []
for name in ('exact-before.json','candidate-cache-snapshots.json','face-pilot-snapshots.json'):
    before = json.loads((folder/name).read_text(encoding='utf-8'))
    rows = []
    for first, second in zip(before['cases'],after['cases'],strict=True):
        assert first['traffic'] == second['traffic']
        assert first['snapshots'] == second['snapshots']
        rows.append({'traffic':second['traffic'],'snapshots_all_equal':True,'ticks':len(second['snapshots']),
                     'before_s':first['seconds'],'after_s':second['seconds']})
    comparisons.append({'baseline':name,'cases':rows})
report = {'passed':True,'comparisons':comparisons,'src_files':{
    str(path.relative_to(root)):hashlib.sha256(path.read_bytes()).hexdigest()
    for path in (root/'src').iterdir() if path.suffix in ('.py','.c','.pyd')}}
(folder/'wheel-production-comparison.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
print(json.dumps(comparisons))
