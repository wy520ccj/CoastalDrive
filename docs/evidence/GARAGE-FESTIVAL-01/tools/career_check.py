"""从静止以正常键盘请求实跑生涯六赛，保存逐拍输入/道路状态并独立复核判定。"""

import argparse
import gzip
import json
import math
import sys
from dataclasses import asdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'src'))

from slalom_driver import apply_keys
from sprint_route_probe import SprintDriver

from career import EVENTS
from career_run import CareerRun
from driver_assist import steering_limit
from race import BestTimes, GameMode
from session import Phase, Session
from simulation import Control
from vehicle_designs import vehicle_design


class CareerDriver:
    def __init__(self, session, event):
        self.session, self.event = session, event
        self.driver = SprintDriver(session.simulation.road, session.vehicle_config, 70.)

    def sample(self):
        session, event = self.session, self.event
        state, result = session.current, session.highway.snapshot.career
        car, distance = state.player, result.position
        if event.id == 'first-drive':
            return Control(throttle=1.)
        if event.kind == 'parking':
            target = 45./3.6
            braking = distance >= event.distance-13.
            return Control(throttle=float(not braking and car.speed < target),
                           brake=float(braking or car.speed > target+1))
        if event.kind == 'slalom':
            look = 5+abs(car.speed)*.45
            old_y, old_x, target_x = 60., 0., 0.
            for y, x in event.gates:
                if distance+look <= y:
                    t = max(0., min(1., (distance+look-old_y)/(y-old_y)))
                    target_x = old_x+(x-old_x)*.5*(1-math.cos(math.pi*t))
                    break
                old_y, old_x = y, x
            dx = target_x-car.position[0]
            error = math.atan2(-dx, look)-math.radians(car.heading)
            angle = math.degrees(math.atan2(5.4*math.sin(error), math.hypot(dx, look)))
            steer = -angle/steering_limit(car.speed, session.vehicle_config)
            speed_error = 45./3.6-car.speed
            return Control(steering=0. if abs(steer) < .08 else math.copysign(1., steer),
                           throttle=float(speed_error > -.25), brake=float(speed_error < -1.))
        return self.driver.sample(state, 1/120)


def check(output, event_ids, design_id='reference-rwd'):
    output.mkdir(parents=True, exist_ok=False)
    cases = []
    for event in EVENTS:
        if event_ids and event.id not in event_ids:
            continue
        session = Session(track='endless', scores=BestTimes(output/'unused-best.json'),
                          vehicle_config=vehicle_design(design_id).config)
        try:
            session.start(mode=GameMode.CAREER, track='endless', career_event_id=event.id,
                          countdown=False, settle_initial=True)
            driver = CareerDriver(session, event)
            initial = session.current.tick
            check_run = CareerRun(event.id, session.highway.snapshot.career.start_progress, session.vehicle_config)
            rows = []
            for _ in range(int(event.limit*120)+2):
                apply_keys(session.keyboard, driver.sample())
                session.tick()
                state, result = session.current, session.highway.snapshot.career
                car = session.simulation.road.lane_frame(state.player)
                progress = session.highway_progress(state)
                actual = check_run.update(progress, result.elapsed, lateral=car.position[0], heading=car.heading,
                    speed=math.hypot(*state.player.velocity[:2]), collisions=state.collisions,
                    reset='player_reset' in state.events)
                assert actual == result
                rows.append({'tick': state.tick, 'progress': progress, 'lateral': car.position[0],
                    'heading': car.heading, 'speed': math.hypot(*state.player.velocity[:2]), 'keys': sorted(session.keyboard.pressed),
                    'control': asdict(session.last_control), 'collisions': state.collisions, 'result': asdict(result)})
                if session.phase == Phase.RESULTS:
                    break
            with gzip.open(output/(event.id+'.json.gz'), 'wt', encoding='utf-8') as stream:
                json.dump(rows, stream, ensure_ascii=False)
            cases.append({'event': event.id, 'config': asdict(session.vehicle_config),
                          'initial_tick': initial, 'steps': len(rows), 'result': asdict(result)})
            print(event.id, result.stars, round(result.elapsed, 3), result.reason, flush=True)
        finally:
            session.close()
    summary = {'passed': all(case['result']['succeeded'] for case in cases), 'design_id': design_id, 'cases': cases,
               'scope': '静止起步/正常二值输入/唯一物理世界，每拍独立复核新规则；非人工试玩'}
    (output/'summary.json').write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding='utf-8')
    return summary['passed']


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--events', nargs='*')
    parser.add_argument('--design', default='reference-rwd')
    args = parser.parse_args()
    raise SystemExit(0 if check(args.output.resolve(), args.events, args.design) else 1)
