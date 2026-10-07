import json
from pathlib import Path

folder=Path(__file__).resolve().parent
before=json.loads((folder/'edge-production-snapshots.json').read_text(encoding='utf-8'))
after=json.loads((folder/'bounds-production-snapshots.json').read_text(encoding='utf-8'))
rows=[]
for first,second in zip(before['cases'],after['cases'],strict=True):
    assert first['snapshots']==second['snapshots']
    rows.append({'traffic':second['traffic'],'snapshot_all_fields_equal':True,'ticks':len(second['snapshots']),
                 'before_s':first['seconds'],'after_s':second['seconds']})
report={'passed':True,'cases':rows,'kind':'healthy GR86 48-tick comparison; saved highway failure is a separate changed-behavior regression'}
(folder/'bounds-production-comparison.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
print(json.dumps(report))
