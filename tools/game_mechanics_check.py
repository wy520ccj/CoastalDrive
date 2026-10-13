"""对照机械积分频率的制动/操稳；实验台初始化复用，覆写仅限诊断进程。"""

import argparse
import json
import math
import sys
from dataclasses import asdict, replace
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, default=ROOT/'src')
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--substeps', type=int, choices=(1, 2), required=True)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=False)
    sys.path.insert(0, str(args.source.resolve()))
    import paths
    paths.resource_root = lambda: ROOT
    import lab_experiment
    from driver_assist import GAME_INPUT
    from driving_modes import DrivingMode
    from lab_experiment import LabExperiment, LabOptions
    from vehicle_designs import DESIGN_VEHICLES
    from vehicle_state import Control, VehicleCommand

    original_signals = lab_experiment.sample_signals

    def signals(snapshot, command, start_time):
        if isinstance(command, Control):
            command = VehicleCommand(steering=snapshot.player.steering,
                                     throttle=command.throttle, brake=command.brake)
        return original_signals(snapshot, command, start_time)

    lab_experiment.sample_signals = signals

    original = DrivingMode.configured_vehicle

    def configured(mode, *a, **kw):
        return replace(original(mode, *a, **kw), tire_substeps=args.substeps)

    DrivingMode.configured_vehicle = configured
    results = []
    for design in DESIGN_VEHICLES:
        for maneuver, friction in (('braking', 1.1), ('braking', .6), ('keyboard', 1.1)):
            options = LabOptions(vehicle_id=design.id, speed_kph=100., duration=8.,
                                 maneuver='manual' if maneuver == 'keyboard' else maneuver,
                                 friction=friction, esc_enabled=True)
            run = LabExperiment(options)
            sim = run.experiment.simulation
            sim.player.assist.input_config = GAME_INPUT
            rows = []
            try:
                while not run.done:
                    tick = len(rows)
                    if maneuver == 'keyboard':
                        action = Control(steering=1. if tick < 36 else -1. if tick < 72 else 0.)
                        # 手感用游戏Control真实推进；实验台正式路径仍为VehicleCommand。
                        state = run.step(action)
                    else:
                        state = run.step()
                    row = asdict(state.player)
                    if not all(math.isfinite(value) for value in
                               (*row['position'], *row['velocity'], row['heading'], row['roll'], row['pitch'])):
                        raise ArithmeticError('真实车辆状态出现非有限值')
                    rows.append(row)
                summary = run.summary()
                summary.update(vehicle=design.id, maneuver=maneuver, friction=friction,
                               substeps=args.substeps, peak_roll=max(abs(row['roll']) for row in rows),
                               final_yaw=rows[-1]['dynamics']['yaw_rate'],
                               final_speed=rows[-1]['speed'],
                               collisions=sim.collision_count-run.initial_collisions)
                if maneuver == 'keyboard':
                    summary.update(release_angle=rows[71]['steering'],
                                   first_release_angle=rows[72]['steering'],
                                   angle_after_300ms=rows[107]['steering'])
                results.append(summary)
                (args.output/f'{design.id}-{maneuver}-{friction}.json').write_text(
                    json.dumps({'summary': summary, 'rows': rows}), encoding='utf-8')
                print(design.id, maneuver, friction, summary['reason'], summary['distance_m'])
            finally:
                run.close()
    (args.output/'summary.json').write_text(json.dumps(results, indent=2), encoding='utf-8')


if __name__ == '__main__':
    main()
