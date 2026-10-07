import json
from pathlib import Path

folder=Path(__file__).resolve().parent
before=json.loads((folder/'bounds-production-snapshots.json').read_text(encoding='utf-8'))
after=json.loads((folder/'bounds-cache-snapshots.json').read_text(encoding='utf-8'))
rows=[]
for first,second in zip(before['cases'],after['cases'],strict=True):
    assert first['snapshots']==second['snapshots']
    rows.append({'traffic':second['traffic'],'snapshot_all_fields_equal':True,'ticks':len(second['snapshots']),
                 'before_s':first['seconds'],'after_s':second['seconds']})
(folder/'bounds-cache-comparison.json').write_text(json.dumps({'passed':True,'cases':rows},indent=2),encoding='utf-8')
print(json.dumps(rows))
