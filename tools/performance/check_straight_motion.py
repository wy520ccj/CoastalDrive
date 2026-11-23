"""默认入口的平直高速真实行驶，记录物理、插值、相机与实际Draw。"""

import argparse
import multiprocessing
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'tools/environment'))

from check_drive_continuity import run
from check_interactive_local_drive import DrivingProbe

from race import GameMode
from simulation import Control


class AccelerationDriver:
    def bind(self, simulation):
        self.simulation = simulation

    def sample(self, state, dt):
        return Control(throttle=1.)


def start(app, task):
    if app._workspace_steps is not None:
        return task.again
    app.session.road_shape = 'straight'
    app.probe_requested = time.perf_counter()
    app.start_game(mode=GameMode.FREE_DRIVE, track='endless')
    return task.done


if __name__ == '__main__':
    multiprocessing.freeze_support()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--accelerate', action='store_true')
    args = parser.parse_args()
    DrivingProbe.probe_start = start
    if args.accelerate:
        import check_drive_continuity
        import check_interactive_local_drive

        original_check = check_drive_continuity.check

        def long_check(*values, **kwargs):
            return original_check(*values, **kwargs, end_distance=900)

        check_drive_continuity.check = long_check
        check_interactive_local_drive.ViewDriver = AccelerationDriver
    run(args.output.resolve(), trace_draw=True)
