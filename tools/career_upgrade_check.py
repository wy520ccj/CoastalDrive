"""真实120Hz生涯改装对照；动力同为全油门，悬架重放原车正常键盘序列。"""

import argparse
import gzip
import json
import math
import sys
from dataclasses import asdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'src'))

from career_check import CareerDriver
from slalom_driver import apply_keys

from career import EVENT_BY_ID
from career_run import CareerRun
from career_tuning import install
from race import BestTimes, GameMode
from session import Phase, Session
from vehicle_designs import vehicle_design
from vehicle_workspace import WorkspaceVehicle


def drive(output, name, vehicle, event_id, replay=None):
    event = EVENT_BY_ID[event_id]
    session = Session(track='endless', scores=BestTimes(output/'unused.json'), vehicle_config=vehicle.config)
    rows = []
    try:
        session.start(mode=GameMode.CAREER, track='endless', career_event_id=event_id,
                      countdown=False, settle_initial=True)
        driver = CareerDriver(session, event)
        verifier = CareerRun(event_id, session.highway.snapshot.career.start_progress, session.vehicle_config)
        for index in range(int(event.limit*120)+2):
            if replay is None:
                apply_keys(session.keyboard, driver.sample())
            else:
                session.keyboard.clear()
                for key in replay[min(index, len(replay)-1)]['keys']:
                    session.keyboard.press(key)
            keys = sorted(session.keyboard.pressed)
            session.tick()
            state, result = session.current, session.highway.snapshot.career
            car = session.simulation.road.lane_frame(state.player)
            progress = session.highway_progress(state)
            checked = verifier.update(progress, result.elapsed, lateral=car.position[0], heading=car.heading,
                speed=math.hypot(*state.player.velocity[:2]), collisions=state.collisions,
                reset='player_reset' in state.events)
            assert checked == result
            rows.append({'tick': state.tick, 'seconds': result.elapsed, 'distance': result.position,
                'speed': state.player.speed, 'roll_deg': state.player.roll, 'pitch_deg': state.player.pitch,
                'lateral': car.position[0], 'keys': keys, 'control': asdict(session.last_control),
                'collisions': state.collisions, 'result': asdict(result)})
            if session.phase == Phase.RESULTS:
                break
        with gzip.open(output/(name+'.json.gz'), 'wt', encoding='utf-8') as stream:
            json.dump(rows, stream, ensure_ascii=False)
        moving = [row for row in rows if row['distance'] > 80. and row['speed'] > 8.]
        metrics = {'steps': len(rows), 'result': asdict(result), 'config': asdict(session.vehicle_config),
            'peak_roll_deg': max(abs(row['roll_deg']) for row in moving),
            'rms_roll_deg': math.sqrt(sum(row['roll_deg']**2 for row in moving)/len(moving)),
            'collisions': max(row['collisions'] for row in rows)}
        print(name, result.stars, round(result.elapsed, 3),
              'roll', round(metrics['peak_roll_deg'], 4), flush=True)
        return rows, metrics
    finally:
        session.close()


def check(output, designs):
    output.mkdir(parents=True, exist_ok=False)
    cases = []
    for design_id in designs:
        vehicle = WorkspaceVehicle(design_id, vehicle_design(design_id).config)
        path = output/design_id/'vehicle.json'
        vehicle.save(path)
        power = install(vehicle, 'street-power', path)
        suspension = install(vehicle, 'sport-suspension', path)
        _, stock_power = drive(output, design_id+'-power-stock', vehicle, 'first-drive')
        _, tuned_power = drive(output, design_id+'-power-upgrade', power, 'first-drive')
        replay, stock_suspension = drive(output, design_id+'-suspension-stock', vehicle, 'slalom')
        rows, tuned_suspension = drive(output, design_id+'-suspension-upgrade', suspension, 'slalom', replay)
        same_inputs = all(a['keys'] == b['keys'] for a, b in zip(replay, rows))
        cases.append({'design_id': design_id, 'power': {'stock': stock_power, 'upgrade': tuned_power},
            'suspension': {'stock': stock_suspension, 'upgrade': tuned_suspension, 'same_inputs': same_inputs}})
    passed = all(case['power']['upgrade']['result']['elapsed'] < case['power']['stock']['result']['elapsed']
        and case['suspension']['same_inputs']
        and all(item['result']['succeeded'] and item['collisions'] == 0
                for topic in ('power', 'suspension') for key, item in case[topic].items() if key != 'same_inputs')
        for case in cases)
    report = {'passed': passed, 'cases': cases,
        'new_driving_steps': sum(item['steps'] for case in cases for topic in ('power', 'suspension')
                                 for key, item in case[topic].items() if key != 'same_inputs'),
        'scope': '真实Simulation/120Hz/正常键盘/逐拍独立规则复核；动力全油门，悬架同一键序列；非人工体验或普遍更快的保证'}
    (output/'summary.json').write_text(json.dumps(report, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
    return passed


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', required=True, type=Path)
    parser.add_argument('--designs', nargs='+', default=['game-tuned', 'coastal-hatch'])
    args = parser.parse_args()
    raise SystemExit(0 if check(args.output.resolve(), args.designs) else 1)
