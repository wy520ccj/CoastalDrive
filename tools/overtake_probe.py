"""测量原生车流中的真实超越机会；试车策略只输出Control，不改物理状态。"""

import argparse
import gzip
import json
import sys
import time
from dataclasses import asdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'src'))

from driving_modes import DrivingMode
from highway_driver import HighwayDriver
from lab_records import model_fingerprint
from lab_runtime import runtime_fingerprint
from simulation import FIXED_DT, Simulation


class OvertakeDriver:
    def __init__(self, road, config, input_config, speed=40.):
        self.road = road
        self.driver = HighwayDriver(1, 41, config=config, input_config=input_config)
        self.driver.cruise = self.driver.preferred_speed = self.driver.target_speed = speed
        # 只固定试车员的意图；道路交通仍执行各自原始风格和随机变速。
        self.driver.speed_clock = 1e9
        self.steps = 0

    def sample(self, state, dt):
        car, traffic = state.player, state.traffic
        if self.steps % 6 == 0:
            self.driver.plan(car, traffic, self.road, [])
        self.steps += 1
        return self.driver.control(car, traffic, self.road,
                                   [self.road.locate(item) for item in (car, *traffic)])


def probe(output, seed, speed):
    output.mkdir(parents=True, exist_ok=False)
    source, runtime = model_fingerprint(), runtime_fingerprint()
    config = DrivingMode.GAME.configured_vehicle()
    sim = Simulation(seed, track='endless', road_shape='straight', traffic_count=12, traffic_span=540,
                     config=config, input_config=DrivingMode.GAME.input_config)
    rows, passes, previous, seen = [], [], {}, set()
    started = time.perf_counter()
    try:
        sim.settle_initial()
        state = sim.snapshot()
        driver = OvertakeDriver(sim.road, config, DrivingMode.GAME.input_config, speed)
        origin = state.player.position[1]+state.origin_y
        initial = asdict(state)
        for _ in range(120*120):
            request = driver.sample(state, FIXED_DT)
            sim.step(request)
            state = sim.snapshot()
            x, y, _ = state.player.position
            for slot, other in enumerate(state.traffic):
                key = slot, other.generation
                delta = other.position[1]-y
                if key in previous and previous[key] > 0 >= delta and key not in seen:
                    passes.append({'slot': slot, 'generation': other.generation, 'distance': y+state.origin_y-origin,
                                   'lateral': abs(other.position[0]-x), 'seconds': state.time-initial['time']})
                    seen.add(key)
                previous[key] = delta
            rows.append({'tick': state.tick, 'time': state.time, 'origin_y': state.origin_y,
                         'player': car_record(state.player), 'traffic': [car_record(item) for item in state.traffic],
                         'collisions': state.collisions, 'control': asdict(request)})
            if y+state.origin_y-origin >= 2000 or state.collisions:
                break
        with gzip.open(output/'raw.json.gz', 'wt', encoding='utf-8') as stream:
            json.dump(rows, stream)
        result = {'initial': initial, 'seed': seed, 'target_speed': speed, 'passes': passes,
                  'rows': len(rows), 'distance': y+state.origin_y-origin, 'collisions': state.collisions,
                  'config': asdict(config), 'source_start': source, 'source_end': model_fingerprint(),
                  'runtime_start': runtime, 'runtime_end': runtime_fingerprint(),
                  'wall_seconds': time.perf_counter()-started, 'scope': '真实Control试车测量，非人工/非最终规则'}
        (output/'summary.json').write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
        print(json.dumps({key: result[key] for key in ('rows', 'distance', 'collisions', 'passes', 'wall_seconds')}), flush=True)
        assert result['source_start'] == result['source_end'] and result['runtime_start'] == result['runtime_end']
    finally:
        sim.close()


def car_record(car):
    return {'position': car.position, 'velocity': car.velocity, 'heading': car.heading,
            'speed': car.speed, 'active': car.active, 'generation': car.generation}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--seed', type=int, default=17)
    parser.add_argument('--speed', type=float, default=40.)
    args = parser.parse_args()
    probe(args.output.resolve(), args.seed, args.speed)
