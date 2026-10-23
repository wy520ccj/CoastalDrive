"""用真实Bullet撞击复现退出，保存失败前状态；不读取玩家存档或改变碰撞规则。"""

import argparse
import json
import sys
import traceback
from dataclasses import asdict, replace
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'src'))

from panda3d.core import Vec3

from driving_modes import DrivingMode
from simulation import Control, Simulation
from vehicle_designs import vehicle_design


def check(output, designs, steps, substeps=None):
    output.mkdir(parents=True, exist_ok=False)
    cases = []
    for design in designs:
        for vx, vy in ((8., 12.), (22., 35.), (35., 0.)):
            for braking in (False, True):
                name = f'{design}-{vx:g}-{vy:g}-{int(braking)}'
                config = DrivingMode.GAME.configured_vehicle(base_config=vehicle_design(design).config)
                if substeps is not None:
                    config = replace(config, tire_substeps=substeps)
                simulation = Simulation(track='highway', traffic_count=0, config=config,
                                        input_config=DrivingMode.GAME.input_config)
                case = {'name': name, 'config': asdict(config), 'passed': False, 'impacts': 0}
                try:
                    simulation.reset_player((5.8, 30., .55))
                    simulation.player._chassis.setLinearVelocity(Vec3(vx, vy, 0))
                    simulation.player.tires.initialize_rolling(vy)
                    control = Control(brake=float(braking), throttle=float(not braking))
                    for _ in range(steps):
                        case['before'] = asdict(simulation.snapshot())
                        simulation.step(control)
                        case['impacts'] += len(simulation.snapshot().impacts)
                    case['after'] = asdict(simulation.snapshot())
                    case['passed'] = case['impacts'] > 0
                except (ArithmeticError, AssertionError, ValueError, RuntimeError):
                    case['exception'] = traceback.format_exc()
                finally:
                    simulation.close()
                cases.append(case)
                (output/(name+'.json')).write_text(json.dumps(case, ensure_ascii=False, indent=2), encoding='utf-8')
                print(name, case['passed'], case['before']['tick'], case.get('exception', '').splitlines()[-1:], flush=True)
    passed = all(case['passed'] for case in cases)
    (output/'summary.json').write_text(json.dumps({'passed': passed, 'cases': [
        {key: value for key, value in case.items() if key not in ('config', 'before', 'after')}
        for case in cases]}, ensure_ascii=False, indent=2), encoding='utf-8')
    return passed


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--designs', nargs='+', default=['game-tuned', 'gr86-2022-premium-6mt', 'subaru-wrx-sti'])
    parser.add_argument('--steps', type=int, default=240)
    parser.add_argument('--substeps', type=int)
    args = parser.parse_args()
    raise SystemExit(0 if check(args.output.resolve(), args.designs, args.steps, args.substeps) else 1)
