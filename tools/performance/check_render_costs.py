"""正常随车的主线程分项；CPU只使用累计值，剖析样本不作性能验收。"""

import argparse
import cProfile
import json
import multiprocessing
import pstats
import sys
import time
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT/'tools/environment'))

import check_interactive_local_drive
from check_interactive_local_drive import DrivingProbe, check

from session import Phase


class CostProbe(DrivingProbe):
    def __init__(self, *args, **kwargs):
        self.costs = defaultdict(lambda: [0, 0., 0.])
        self.profile = cProfile.Profile()
        self.profiling = False
        super().__init__(*args, **kwargs)

    def measured(self, name, call, task):
        if not self.profiling:
            return call(task)
        wall, cpu = time.perf_counter(), time.thread_time()
        result = call(task)
        row = self.costs[name]
        row[0] += 1
        row[1] += time.perf_counter()-wall
        row[2] += time.thread_time()-cpu
        return result

    def _ShowBase__igLoop(self, task):
        return self.measured('renderFrame', super()._ShowBase__igLoop, task)

    def _ShowBase__garbageCollectStates(self, task):
        return self.measured('state_collection', super()._ShowBase__garbageCollectStates, task)

    def update(self, task):
        return self.measured('game_update', super().update, task)

    def pace_frame(self, task):
        return self.measured('frame_pacing', super().pace_frame, task)

    def probe_frame(self, task):
        if self.probe_driver and self.session.phase == Phase.DRIVING and not self.profiling:
            self.profile.enable()
            self.profiling = True
        return super().probe_frame(task)

    def probe_finish(self):
        self.profile.disable()
        self.profiling = False
        self.profile.dump_stats(str(self.probe_output/'main-thread.prof'))
        with (self.probe_output/'main-thread.txt').open('w', encoding='utf-8') as stream:
            pstats.Stats(self.profile, stream=stream).strip_dirs().sort_stats('cumulative').print_stats(65)
        (self.probe_output/'costs.json').write_text(json.dumps({
            'scope': '主线程短剖析；CPU累计量仍受15.625ms计时粒度影响，不能用单次0ms推断免费。各项不含独立物理/Draw线程；非性能通过样本',
            'costs': {name: {'calls': row[0], 'wall_total_s': row[1], 'thread_cpu_total_s': row[2],
                             'wall_mean_ms': row[1]*1000/row[0], 'thread_cpu_mean_ms': row[2]*1000/row[0]}
                      for name, row in self.costs.items()}}, ensure_ascii=False, indent=2), encoding='utf-8')
        super().probe_finish()


if __name__ == '__main__':
    multiprocessing.freeze_support()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    check_interactive_local_drive.DrivingProbe = CostProbe
    check(args.output.resolve(), False, False)
