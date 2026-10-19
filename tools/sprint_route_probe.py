"""在原权威道路测量短途键盘驾驶；先测路线，再确定赛事计时目标。"""

import argparse
import gzip
import hashlib
import json
import math
import sys
import time
from dataclasses import asdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'src'))

from slalom_driver import apply_keys

from controls import KeyboardController
from driver_assist import steering_limit
from driving_modes import DrivingMode
from lab_records import model_fingerprint
from lab_runtime import runtime_fingerprint
from simulation import FIXED_DT, Control, Simulation
from sprint_routes import SPRINT_ROUTES


class SprintDriver:
    def __init__(self, road, config, speed_kph):
        self.road, self.config, self.speed = road, config, speed_kph/3.6

    def sample(self, state, dt):
        car = state.player
        progress, _ = self.road.locate(car)
        look = 6+abs(car.speed)*.65
        target = self.road.sample_lateral(progress+look, 0.)
        dx, dy = target.x-car.position[0], target.y-car.position[1]
        error = math.atan2(-dx, dy)-math.radians(car.heading)
        angle = math.degrees(math.atan2(5.4*math.sin(error), math.hypot(dx, dy)))
        steer = -angle/steering_limit(car.speed, self.config)
        speed_error = self.speed-car.speed
        # 二值请求进入原KeyboardController，车速转向辅助及正常机械执行器保持。
        return Control(steering=0. if abs(steer) < .06 else math.copysign(1., steer),
                       throttle=float(speed_error > -.25), brake=float(speed_error < -1.))


def probe(output, speeds):
    output.mkdir(parents=True, exist_ok=False)
    source, runtime = model_fingerprint(), runtime_fingerprint()
    summaries = []
    for mode, route in SPRINT_ROUTES.items():
        for speed in speeds:
            config = DrivingMode.GAME.configured_vehicle()
            sim = Simulation(route.seed, track='endless', road_shape=route.shape, traffic_count=0,
                             config=config, input_config=DrivingMode.GAME.input_config)
            rows = []
            started = time.perf_counter()
            try:
                sim.settle_initial()
                keyboard = KeyboardController(DrivingMode.GAME.input_config)
                driver = SprintDriver(sim.road, config, speed)
                state = sim.snapshot()
                origin, _ = sim.road.locate(state.player)
                previous_progress, previous_time = 0., 0.
                gate_times = []
                start_time = state.time
                for _ in range(180*120):
                    apply_keys(keyboard, driver.sample(state, FIXED_DT))
                    request = keyboard.sample(state, FIXED_DT)
                    sim.step(request)
                    state = sim.snapshot()
                    progress, lateral = sim.road.locate(state.player)
                    distance, elapsed = progress-origin, state.time-start_time
                    while len(gate_times) < len(route.gates) and previous_progress < route.gates[len(gate_times)] <= distance:
                        fraction = (route.gates[len(gate_times)]-previous_progress)/(distance-previous_progress)
                        gate_times.append(previous_time+(elapsed-previous_time)*fraction)
                    rows.append({'tick': state.tick, 'time': state.time, 'position': state.player.position,
                        'velocity': state.player.velocity, 'heading': state.player.heading,
                        'distance': distance, 'lateral': lateral, 'collisions': state.collisions,
                        'keys': sorted(keyboard.pressed), 'request': asdict(request)})
                    previous_progress, previous_time = distance, elapsed
                    if len(gate_times) == len(route.gates) or state.collisions or abs(lateral) > 6.5:
                        break
                name = mode.value+f'-{speed:g}'
                with gzip.open(output/(name+'.json.gz'), 'wt', encoding='utf-8') as stream:
                    json.dump(rows, stream, ensure_ascii=False)
                result = {'mode': mode.value, 'target_kph': speed, 'route': asdict(route), 'origin': origin,
                    'config': asdict(config), 'input': asdict(keyboard.input_config), 'gate_times': gate_times,
                    'collisions': state.collisions, 'distance': distance, 'rows': len(rows),
                    'max_lateral': max(abs(row['lateral']) for row in rows),
                    'finished': len(gate_times) == len(route.gates), 'compute_wall_seconds': time.perf_counter()-started}
                summaries.append(result)
                print(json.dumps({key: result[key] for key in ('mode', 'target_kph', 'gate_times', 'collisions', 'finished', 'max_lateral')}), flush=True)
            finally:
                sim.close()
    source_end, runtime_end = model_fingerprint(), runtime_fingerprint()
    unchanged = source == source_end and runtime == runtime_end
    (output/'summary.json').write_text(json.dumps({'cases': summaries, 'source_start': source,
        'source_end': source_end, 'runtime_start': runtime, 'runtime_end': runtime_end, 'passed': unchanged,
        'tool_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        'scope': '原道路实际键盘测量，尚非最终赛事规则验收；非人工驾驶', 'human_gate': 'pending'},
        ensure_ascii=False, indent=2), encoding='utf-8')
    if not unchanged:
        raise RuntimeError('测量期间源码或SDK改变；原始结果保留，不计作最终版本验收')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--speeds', nargs='+', type=float, default=[90., 65., 45.])
    args = parser.parse_args()
    probe(args.output.resolve(), args.speeds)
