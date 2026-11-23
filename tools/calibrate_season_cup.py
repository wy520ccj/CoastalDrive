"""为自选车综合杯生成同车型、同赛道的实跑门槛和证据。"""

import argparse
import hashlib
import json
import math
import sys
from concurrent.futures import ProcessPoolExecutor
from dataclasses import asdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'src'))

from career_garage import CAR_BY_DESIGN
from challenge_build import BuildDraft
from challenge_calibration import checked_sample
from challenge_catalog import course_track
from race import BestTimes, GameMode
from road_test_driver import RoadTestDriver
from season_cup import CUP_LEGS, cup_base_spec
from session import Phase, Session


def run(job):
    output, design_id, mode, policy = job
    folder = output/design_id/mode.value
    folder.mkdir(parents=True, exist_ok=False)
    spec = cup_base_spec(design_id, mode)
    session = Session(track='test', scores=BestTimes(folder/'isolated.json'))
    try:
        session.start(mode=mode, track=course_track(mode), countdown=False, settle_initial=True,
                      challenge_spec=spec, build=BuildDraft())
        driver = RoadTestDriver(mode, spec.id, session.road_shape, sprint_version=spec.version)
        driver.policy.update(policy)
        driver.bind(session.simulation)
        session.set_controller(driver)
        try:
            for _ in range(120*180):
                session.tick()
                if session.phase == Phase.RESULTS:
                    break
        except ArithmeticError as error:
            (folder/'failure.json').write_text(json.dumps(
                {'error': str(error), 'tick': session.current.tick,
                 'snapshot': asdict(session.current), 'control': asdict(session.last_control)},
                ensure_ascii=False, default=str), encoding='utf-8')
            return design_id, mode.value, {'failure': str(error), 'tick': session.current.tick}
        if session.phase == Phase.DRIVING:
            session.finish()
        status = session.highway.snapshot.engineering
        path = Path(status.trace_path)
        raw = path.read_bytes()
        row = {'rules': spec.version, 'shape': spec.road_shape, 'trace': str(path),
               'sha256': hashlib.sha256(raw).hexdigest(), 'policy': driver.policy,
               'collisions': session.current.collisions}
        if status.result.valid and not session.current.collisions:
            if mode == GameMode.HILL_TRAFFIC:
                assert session.highway.snapshot.overtake.succeeded
            sample = checked_sample(spec, json.loads(raw), agent=True)
            row.update(seconds=sample['seconds'], consumption=sample['consumption'],
                       targets=[[math.ceil(sample['seconds']*factor*10)/10,
                                 math.ceil(sample['consumption']*factor*10)/10]
                                for factor in (1.25, 1.12, 1.03)])
        else:
            row['failure'] = session.highway.snapshot.reason or status.result.notice
        return design_id, mode.value, row
    finally:
        session.close()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', required=True, type=Path)
    parser.add_argument('--cars', nargs='+', choices=tuple(CAR_BY_DESIGN), default=tuple(CAR_BY_DESIGN))
    parser.add_argument('--modes', nargs='+', choices=[mode.value for mode in CUP_LEGS],
                        default=[mode.value for mode in CUP_LEGS])
    parser.add_argument('--workers', type=int, default=3)
    parser.add_argument('--target-kph', type=float)
    parser.add_argument('--curve-acceleration', type=float)
    args = parser.parse_args()
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=False)
    policy = {key: value for key, value in (('target_kph', args.target_kph),
                                            ('curve_acceleration', args.curve_acceleration)) if value is not None}
    jobs = [(output, car, GameMode(mode), policy) for car in args.cars for mode in args.modes]
    results = {car: {} for car in args.cars}
    with ProcessPoolExecutor(max_workers=args.workers) as pool:
        for car, mode, row in pool.map(run, jobs):
            results[car][mode] = row
            print(car, mode, row.get('failure', row.get('seconds')), flush=True)
            (output/'summary.json').write_text(json.dumps(results, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
    return int(any('failure' in row for car in results.values() for row in car.values()))


if __name__ == '__main__':
    sys.exit(main())
