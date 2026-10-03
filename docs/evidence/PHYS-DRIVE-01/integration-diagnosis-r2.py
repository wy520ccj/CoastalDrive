"""冻结候选的真实ABS、离合释放与空中转子诊断；不改生产参数或测试。"""

import hashlib
import json
import sys
from dataclasses import replace
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path[:0] = [str(ROOT / 'src'), str(ROOT / 'tools')]

from physics import abs_probe, esc_probe, tcs_probe
from physics.reference_ab import _write_csv
from driving_modes import REFERENCE_CAR

OUT = Path(__file__).with_suffix('')
OUT.mkdir(exist_ok=False)


def hashes():
    return {p.relative_to(ROOT).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
            for folder in ('src', 'tests', 'tools') for p in sorted((ROOT / folder).rglob('*.py'))}


before = hashes()
results = []
for label, config in (
        ('current', REFERENCE_CAR),
        ('strong-brake-design', replace(REFERENCE_CAR, brake_torque=REFERENCE_CAR.brake_torque * 1.5)),
        ('legacy', replace(REFERENCE_CAR, finite_drivetrain=False))):
    abs_probe.REFERENCE_CAR = config
    for enabled in (False, True):
        summary, rows = abs_probe.run_trial('asphalt', enabled)
        name = f'abs-{label}-{enabled}'
        _write_csv(OUT / f'{name}.csv', rows)
        results.append({'name': name, 'summary': summary})
        print(name, 'lock', summary['locked_wheel_seconds'], 'distance', summary['path_distance_m'], flush=True)
abs_probe.REFERENCE_CAR = REFERENCE_CAR
for enabled in (False, True):
    summary, rows = tcs_probe.run_trial('driver-brake', enabled, duration=3)
    name = f'tcs-release-{enabled}'
    _write_csv(OUT / f'{name}.csv', rows)
    results.append({'name': name, 'summary': summary})
    print(name, 'initial release', [(r['tick'], r['state.powertrain_state.clutch_capacity'],
          r['state.wheel_dynamics.2.drive_torque']) for r in rows[241:252]], flush=True)
for label, config in (
        ('current', REFERENCE_CAR),
        ('legacy', replace(REFERENCE_CAR, finite_drivetrain=False)),
        ('opposite-engine', replace(REFERENCE_CAR, engine_axis=(0., -1., 0.)))):
    for steps in (2, 4, 8, 16):
        summary, rows = esc_probe.run_trial('airborne-recontact', True, 6, 'simulation',
                                           vehicle_config=replace(config, tire_substeps=steps))
        name = f'airborne-{label}-{steps}'
        _write_csv(OUT / f'{name}.csv', rows)
        results.append({'name': name, 'summary': summary})
        print(name, 'yaw', summary['heading_change_deg'], 'peak', summary['peak_abs_unwrapped_heading_deg'],
              'distance', summary['path_distance_m'], flush=True)
report = {'source_before': before, 'source_after': hashes(), 'results': results,
          'protocol': '真实生产Vehicle/Bullet；只在试验开始初始化速度，各明确完整配置写入summary。'
                      '更强制动仅是研究配置，运行默认硬件未改；反曲轴用于旋向负对照。'}
(OUT / 'summary.json').write_text(json.dumps(report, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')
