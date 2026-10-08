import json
import sys
from pathlib import Path
root = Path(__file__).resolve().parents[3]
sys.path[:0] = [str(root / 'src'), str(root / 'tools')]
from physics.tcs_probe import run_trial
for enabled in (False, True):
    summary, rows = run_trial('airborne-recontact', enabled, 2.)
    result = {'summary': summary, 'rows': rows}
    (root / f'logs/physics/PHYS-DESIGN-01-wall/recontact-2s-{enabled}.json').write_text(json.dumps(result, ensure_ascii=False), encoding='utf-8')
    print(enabled, 'finalsupport', [rows[-1][f'state.wheel_dynamics.{i}.sample_support'] for i in range(4)])
    print('support_transitions', [(row['tick'], [row[f'state.wheel_dynamics.{i}.sample_support'] for i in range(4)], row['state.position.2']) for k,row in enumerate(rows) if k == 0 or any(row[f'state.wheel_dynamics.{i}.sample_support'] != rows[k-1][f'state.wheel_dynamics.{i}.sample_support'] for i in range(4))])
