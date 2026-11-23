"""原参数在真实山脊路网的120Hz车身/悬架轨迹；不依赖显示帧率。"""

import argparse
import json
import sys
import time
from collections import Counter
from dataclasses import replace
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT/'src'))
sys.path.insert(0, str(ROOT/'tools/environment'))

from check_driving_composition import ViewDriver

from driving_modes import DrivingMode
from simulation import Control, Simulation
from vehicle_workspace import WorkspaceVehicle


def check(output, substeps, mesh_step):
    output.mkdir(parents=True, exist_ok=False)
    vehicle = WorkspaceVehicle.load()
    import curve_mesh
    import simulation as simulation_module

    curve_mesh.ROAD_STEP = mesh_step
    config = replace(DrivingMode.GAME.configured_vehicle(base_config=vehicle.config), tire_substeps=substeps)
    simulation = Simulation(0, track='endless', road_shape='ridge-club', traffic_count=0, config=config)
    driver = ViewDriver()
    driver.bind(simulation)
    counts = Counter()
    advance = simulation_module.advance_world

    def observed(*args, **kwargs):
        counts[kwargs['substeps']] += 1
        return advance(*args, **kwargs)

    simulation_module.advance_world = observed
    rows = []
    started = time.perf_counter()
    try:
        for _ in range(120):
            simulation.step(Control(brake=1.))
        for _ in range(2640):
            state = simulation.snapshot()
            simulation.step(driver.sample(state, 1/120))
            car = simulation.snapshot().player
            s, d = simulation.road.locate(car)
            pose = simulation.road.sample_lateral(s, d)
            rows.append({'tick': simulation.snapshot().tick, 'distance': s, 'pitch': car.pitch, 'grade': pose.grade,
                         'body_z': car.position[2], 'road_z': pose.z, 'speed': car.speed,
                         'angular_velocity': list(simulation.player._chassis.getAngularVelocity()),
                         'loads': [x.normal_load for x in car.wheel_contacts],
                         'compression': [x.compression for x in car.wheel_contacts]})
        (output/'motion.json').write_text(json.dumps(rows), encoding='utf-8')
        error = np.array([r['pitch']-r['grade'] for r in rows if 150 < r['distance'] < 240])
        report = {'scope': '真实无交通山脊2640新拍，原GT参数，120Hz；配置子步数为下限，包含当前弯坡/碰撞细分，实际次数另列',
                  'substeps': substeps, 'mesh_step': mesh_step, 'vehicle': vehicle.design_id, 'compute_wall_s': time.perf_counter()-started,
                  'effective_substeps_ticks': dict(counts),
                  'pitch_minus_road_percentiles_deg': np.percentile(error, [0, 5, 50, 95, 100]).tolist()}
        (output/'summary.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
        print(report)
    finally:
        simulation.close()
        simulation_module.advance_world = advance


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--substeps', type=int, choices=(1, 2), default=1)
    parser.add_argument('--mesh-step', type=int, choices=(1, 5), default=1)
    args = parser.parse_args()
    check(args.output.resolve(), args.substeps, args.mesh_step)
