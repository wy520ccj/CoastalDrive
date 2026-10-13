"""固定初速短按与松键；输入/执行器/车身分别记录，不以离线结果宣称实时。"""

import argparse
import hashlib
import json
import pickle
import sys
from dataclasses import asdict, replace
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, default=ROOT / 'src')
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--mode', choices=('game', 'simulation'), default='game')
    parser.add_argument('--exact', action='store_true', help='研究执行器完整快照对照')
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=False)
    sys.path.insert(0, str(args.source.resolve()))
    import paths
    paths.resource_root = lambda: ROOT
    from controls import KeyboardController
    from driving_modes import DrivingMode
    from lab_experiment import LabExperiment, LabOptions
    from vehicle_state import FIXED_DT, VehicleCommand

    mode = DrivingMode(args.mode)
    results = []
    for hold in (12, 36, 60):
        run = LabExperiment(LabOptions(vehicle_id='gr86-2022-premium-6mt', speed_kph=100))
        sim = run.experiment.simulation
        sim.player.assist.input_config = mode.input_config
        keyboard = KeyboardController(mode.input_config)
        keyboard.press('d')
        rows, hashes = [], []
        try:
            for tick in range(hold + 180):
                if tick == hold:
                    keyboard.release('d')
                control = keyboard.sample(None, FIXED_DT)
                action = (VehicleCommand(steering=2. if tick < hold else 0., gear=0, clutch=0.)
                          if args.exact else control)
                sim.step(action)
                snapshot = sim.snapshot()
                car = snapshot.player
                normalized = replace(snapshot, contact_epoch=0,
                    impacts=tuple(replace(impact, epoch=0) for impact in snapshot.impacts))
                hashes.append(hashlib.sha256(pickle.dumps(normalized, protocol=5)).hexdigest())
                rows.append({'time': (tick + 1) * FIXED_DT, 'input': asdict(control),
                             'steering': car.steering, 'yaw': car.dynamics.yaw_rate,
                             'heading': car.heading, 'speed': car.speed, 'position': car.position,
                             'ay': car.lateral_acceleration})
            release_angle = rows[hold - 1]['steering']
            peak_index = max(range(hold, len(rows)), key=lambda i: rows[i]['steering'])
            result = {'hold_seconds': hold * FIXED_DT, 'release_angle': release_angle,
                      'post_release_peak': rows[peak_index]['steering'],
                      'post_release_peak_delay': (peak_index - hold + 1) * FIXED_DT,
                      'heading_after_one_second': rows[hold + 119]['heading'],
                      'steering_after_300ms': rows[hold + 35]['steering'],
                      'player_collisions': sim.collision_count}
            results.append(result)
            (args.output / f'hold-{hold}.json').write_text(
                json.dumps({'summary': result, 'rows': rows, 'hashes': hashes}), encoding='utf-8')
        finally:
            run.close()
    (args.output / 'summary.json').write_text(json.dumps(results, indent=2), encoding='utf-8')
    print(json.dumps(results))


if __name__ == '__main__':
    main()
