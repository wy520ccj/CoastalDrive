import json
from pathlib import Path

folder=Path(__file__).resolve().parent
after=json.loads((folder/'edge-production-snapshots.json').read_text(encoding='utf-8'))
comparisons=[]
for name in ('exact-before.json','wheel-production-snapshots.json','edge-pilot-snapshots.json'):
    before=json.loads((folder/name).read_text(encoding='utf-8'))
    rows=[]
    for first,second in zip(before['cases'],after['cases'],strict=True):
        assert first['traffic'] == second['traffic']
        assert first['snapshots'] == second['snapshots']
        rows.append({'traffic':second['traffic'],'snapshots_all_equal':True,'ticks':len(second['snapshots']),
                     'before_s':first['seconds'],'after_s':second['seconds']})
    comparisons.append({'baseline':name,'cases':rows})
(folder/'edge-production-comparison.json').write_text(json.dumps({'passed':True,'comparisons':comparisons},indent=2),encoding='utf-8')
print(json.dumps(comparisons))
