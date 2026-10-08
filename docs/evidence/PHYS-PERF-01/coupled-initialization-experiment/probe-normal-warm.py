"""仅独立进程试验当前接触载荷作为法向未知量初值；收敛判据保持。"""
import json
import sys
from pathlib import Path
root=Path.cwd();folder=root/'logs/physics/PHYS-PERF-01'
sys.path.insert(0,str(root/'src'))
import tire_drivetrain
source=(root/'src/tire_drivetrain.py').read_text(encoding='utf-8')
source=source[source.index('def advance_drivetrain('):]
old='    normal_forces = (0.,) * 4'
new='''    normal_forces = (tuple(frame.load * alignment if frame.supported and contact else 0.
                           for frame, alignment, contact in zip(frames, suspension.alignment, suspension.touching))
                     if suspension is not None else (0.,) * 4)'''
assert old in source
source=source.replace(old,new,1)
(folder/'normal-warm-trial-source.py').write_text(source,encoding='utf-8')
exec(compile(source,'normal warm process-only trial','exec'),tire_drivetrain.__dict__)
import pytest
code=pytest.main(['-q','tests/test_joint_suspension.py','tests/test_guardrail_suspension.py',
                 'tests/test_tire_shaft.py','tests/test_suspension_coupling.py'])
if code:raise SystemExit(code)
snapshot_source=(folder/'tire-constitutive-snapshots.py').read_text(encoding='utf-8')
snapshot_source=snapshot_source.replace("'tire-constitutive-snapshots.json'","'normal-warm-snapshots.json'")
snapshot_source=snapshot_source[:snapshot_source.index('old=json.loads')]
exec(compile(snapshot_source,__file__,'exec'))
baseline=json.loads((folder/'triangle-bound-snapshots.json').read_text(encoding='utf-8'))
current=json.loads((folder/'normal-warm-snapshots.json').read_text(encoding='utf-8'))
report={'pytest_code':int(code),'cases':[{'traffic':a['traffic'],'seconds':a['seconds'],
          'all_snapshots_equal':a['snapshots']==b['snapshots']} for a,b in zip(current['cases'],baseline['cases'])]}
(folder/'normal-warm-trial.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
print(json.dumps(report))
