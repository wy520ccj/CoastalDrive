"""复算归档两条冲刺的原有全部规则字段；不是物理重跑或新SDK执行。"""

import argparse
import gzip
import hashlib
import json
import math
import sys
import tempfile
from dataclasses import asdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'src'))

from lab_records import model_fingerprint
from race import BestTimes, GameMode
from simulation import FIXED_DT
from sprint_run import SprintRun
from traffic import Road
from vehicle_config import CAR
from vehicle_parameters import config_from_document


def check():
    source = model_fingerprint()
    archive = ROOT/'docs/evidence/SPRINT-ROUTES-01'
    manifest = {item['path']: item['sha256'] for item in json.loads((archive/'archive-manifest.json').read_text(encoding='utf-8'))}
    cases = []
    for label in ('normal', 'double'):
        path = archive/label/'summary.json'
        assert hashlib.sha256(path.read_bytes()).hexdigest() == manifest[f'{label}/summary.json']
        summary = json.loads(path.read_text(encoding='utf-8'))
        for case in summary['cases']:
            path = archive/label/case['record']
            assert hashlib.sha256(path.read_bytes()).hexdigest() == manifest[f"{label}/{case['record']}"]
            with gzip.open(path, 'rt', encoding='utf-8') as stream:
                rows = json.load(stream)
            route = case['route']
            road = Road('endless', seed=route['seed'], shape=route['shape'])
            with tempfile.TemporaryDirectory() as temporary:
                item = SprintRun(case['start_progress'], GameMode(case['mode']), BestTimes(Path(temporary)/'best.json'),
                                 case['variant'], config_from_document(case['config'], CAR))
                elapsed = 0.
                for row in rows:
                    progress, lateral = road.curve.project((row['position'][0], row['position'][1]+row['origin_y']))
                    point = road.curve.sample(progress)
                    angle, grade = math.radians(point.heading), math.radians(point.grade)
                    vx, vy, vz = row['velocity']
                    forward = (-vx*math.sin(angle)+vy*math.cos(angle))*math.cos(grade)+vz*math.sin(grade)
                    elapsed += FIXED_DT
                    result = item.update(progress, elapsed, lateral=lateral, heading=(row['heading']-point.heading+180)%360-180,
                        forward_speed=forward, collisions=row['collisions'], reset='player_reset' in row['events'])
                    current = json.loads(json.dumps(asdict(result)))
                    previous = row['sprint']
                    assert set(current)-set(previous) == {'forward_kph', 'gate_kph', 'zone_min_kph', 'zone_max_kph', 'zone_error_at'}
                    assert {name: current[name] for name in previous} == previous, (label, case['mode'], row['tick'])
                    assert result.zone_min_kph is result.zone_max_kph is result.zone_error_at is None
            cases.append({'archive': label, 'mode': case['mode'], 'rows': len(rows), 'seconds': result.seconds,
                          'fields_exact': sorted(previous), 'input_sha256': hashlib.sha256(path.read_bytes()).hexdigest()})
    assert source == model_fingerprint()
    return {'passed': True, 'cases': cases, 'rows': sum(case['rows'] for case in cases),
            'source_start': source, 'source_end': source,
            'kind': '从两库历史真实位置/速度复算全部原规则字段逐拍完全相同；新增观测字段单独列明，不重跑物理'}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise FileExistsError('结果目录已存在，不能覆盖证据')
    result = check()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps({'passed': result['passed'], 'rows': result['rows']}, ensure_ascii=False))
