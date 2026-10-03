"""真实曲轴旋向与镜像对称工况；完整接触列取逐行并集。"""

import csv
import gzip
import hashlib
import json
import sys
from dataclasses import replace
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path[:0] = [str(ROOT / 'src'), str(ROOT / 'tools')]

from physics import esc_probe
from driving_modes import REFERENCE_CAR

OUT = Path(__file__).with_suffix('')
OUT.mkdir(exist_ok=False)


def hashes():
    return {p.relative_to(ROOT).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
            for folder in ('src', 'tests', 'tools') for p in sorted((ROOT / folder).rglob('*.py'))}


report = {'source_before': hashes(), 'results': [],
          'protocol': '真实曲轴默认纵向±y旋向对照；横向x为关于纵向平面满足左右镜像的轴向伪矢量配置。'
                      '参数完整保存；无运行状态修正、无迭代失败重试。'}
for label, axis, substeps in (
        ('current', (0., 1., 0.), (2,)),
        ('opposite-engine', (0., -1., 0.), (2,)),
        ('mirror-symmetric-engine', (1., 0., 0.), (2, 4, 8, 16))):
    for steps in substeps:
        summary, rows = esc_probe.run_trial('airborne-recontact', True, 6, 'simulation',
                vehicle_config=replace(REFERENCE_CAR, engine_axis=axis, tire_substeps=steps))
        name = f'{label}-{steps}'
        report['results'].append({'name': name, 'summary': summary})
        report['source_after'] = hashes()
        (OUT / 'summary.json').write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
        with gzip.open(OUT / f'{name}.csv.gz', 'wt', encoding='utf-8', newline='') as handle:
            writer = csv.DictWriter(handle, sorted({key for row in rows for key in row}))
            writer.writeheader()
            writer.writerows(rows)
        print(name, 'heading', summary['heading_change_deg'], 'peak', summary['peak_abs_unwrapped_heading_deg'],
              'distance', summary['path_distance_m'], 'stop', summary['time_to_stop_s'], flush=True)
