"""按玩家全油门起步复现测速失败；只读当前车，输出到隔离目录。"""

import argparse
import json
import os
import sys
from dataclasses import asdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'src'))

from driving_modes import DrivingMode
from race import BestTimes, GameMode
from session import Phase, Session
from slalom_lesson import SlalomLesson, SlalomScores
from vehicle_designs import vehicle_design
from vehicle_workspace import WorkspaceVehicle
from workshop_cornering import build_config


def probe(output):
    output.mkdir(parents=True, exist_ok=False)
    current = WorkspaceVehicle.load()
    vehicles = [(name, vehicle_design(name).config, {}) for name in
                ('game-tuned', 'reference-rwd', 'reference-fwd', 'reference-awd', 'gr86-2022-premium-6mt')]
    if current is not None:
        vehicles.append(('current-'+current.design_id, current.config, {}))
        settings = json.loads((Path(os.environ['LOCALAPPDATA'])/'CoastalDrive/driving-mode.json').read_text(encoding='utf-8'))
        settings['driving_mode'] = DrivingMode(settings.pop('mode'))
        vehicles.append(('saved-settings-'+current.design_id, current.config, settings))
    results = []
    for name, config, options in vehicles:
        session = Session(scores=BestTimes(output/(name+'-best.json')), vehicle_config=config,
                          **options)
        rows = []
        try:
            session.start(mode=GameMode.FAST_SLALOM, track='endless', countdown=False, settle_initial=True)
            initial = session.current.player.speed
            session.keyboard.press('w')
            for _ in range(4800):
                session.tick()
                result = session.highway.snapshot.slalom
                rows.append({'tick': session.current.tick, 'position': result.position,
                             'speed_kph': session.current.player.velocity[1]*3.6,
                             'throttle': session.last_control.throttle,
                             'brake': session.last_control.brake})
                if session.phase == Phase.RESULTS:
                    break
            record = {'name': name, 'initial_speed': initial, 'steps': len(rows),
                      'config': asdict(session.vehicle_config), 'result': asdict(result), 'rows': rows}
            (output/(name+'.json')).write_text(json.dumps(record, ensure_ascii=False, indent=2), encoding='utf-8')
            results.append({key: record[key] for key in ('name', 'initial_speed', 'steps', 'result')})
        finally:
            session.close()
    (output/'summary.json').write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding='utf-8')
    return results


def complete_fast(output):
    """复核原已验收70k方案，用正常二值按键完成原高速题。"""
    from slalom_driver import SlalomDriver, apply_keys
    output.mkdir(parents=True, exist_ok=False)
    session = Session(scores=BestTimes(output/'best.json'), vehicle_config=build_config(3, False, False))
    rows = []
    try:
        session.start(mode=GameMode.FAST_SLALOM, track='endless', countdown=False, settle_initial=True)
        driver = SlalomDriver(75., session.vehicle_config, origin=session.highway.snapshot.slalom.start_progress)
        for _ in range(4802):
            apply_keys(session.keyboard, driver.sample(session.current, 1/120))
            session.tick()
            result = session.highway.snapshot.slalom
            rows.append({'tick': session.current.tick, 'position': result.position,
                         'speed_kph': session.current.player.velocity[1]*3.6,
                         'elapsed': session.highway.snapshot.elapsed,
                         'player': asdict(session.current.player), 'collisions': session.current.collisions,
                         'control': asdict(session.last_control), 'result': asdict(result)})
            if session.phase == Phase.RESULTS:
                break
        recheck = SlalomLesson(result.start_progress, SlalomScores(output/'recheck-best.json', 'check'),
                              session.vehicle_config, fast=True)
        for row in rows:
            observed = recheck.update(result.start_progress+row['position'], row['player']['velocity'][1],
                row['elapsed'], lateral=row['player']['position'][0], heading=row['player']['heading'],
                collisions=row['collisions'])
            assert asdict(observed) == row['result']
        document = {'passed': result.succeeded, 'rule_recheck': True, 'config': asdict(session.vehicle_config),
                    'result': asdict(result), 'steps': len(rows), 'rows': rows,
                    'scope': '原70k方案真实120Hz/二值按键控速与转向；非人工驾驶，无初速修改'}
        (output/'complete-fast.json').write_text(json.dumps(document, ensure_ascii=False), encoding='utf-8')
        assert result.succeeded, result.reason
        return {key: document[key] for key in ('passed', 'result', 'steps', 'scope')}
    finally:
        session.close()


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--complete-fast', action='store_true')
    args = parser.parse_args()
    print(json.dumps((complete_fast if args.complete_fast else probe)(args.output.resolve()), ensure_ascii=False))
