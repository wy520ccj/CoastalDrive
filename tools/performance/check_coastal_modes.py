"""正常独立120Hz窗口依次驾驶滨海自由/计时；不作为长期性能Gate。"""

import argparse
import json
import multiprocessing
import os
import sys
import time
from dataclasses import asdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT/'src'), str(ROOT/'tools/environment')]

import numpy as np
from check_driving_composition import ViewDriver
from panda3d.core import Filename, WindowProperties

from application import CoastalDrive
from lab_records import model_fingerprint
from race import GameMode
from session import Phase


class CoastalProbe(CoastalDrive):
    def __init__(self, output, *, render_size=(1280,720), workspace_vehicle=None):
        self.probe_output = output
        self.probe_started = time.perf_counter()
        self.probe_rows, self.probe_runs = [], []
        self.probe_modes = (GameMode.FREE_DRIVE, GameMode.TIME_TRIAL)
        self.probe_index = 0
        self.probe_driving = False
        self.probe_captured = False
        self.probe_last = None
        self.probe_after_capture = False
        super().__init__(render_size=render_size,workspace_vehicle=workspace_vehicle)
        properties = WindowProperties()
        properties.setTitle('CoastalDrive · 滨海两模式自动复测')
        properties.setSize(*render_size)
        properties.setFixedSize(True)
        self.win.requestProperties(properties)
        self.taskMgr.doMethodLater(1, self.begin_mode, 'coast-start')
        self.taskMgr.add(self.check_frame, 'coast-probe', sort=99)

    def begin_mode(self, task):
        if self._workspace_steps is not None:
            return task.again
        self.start_game(mode=self.probe_modes[self.probe_index], track='coastal')
        return task.done

    def check_frame(self, task):
        now = time.perf_counter()
        if now-self.probe_started > 150:
            raise TimeoutError('滨海两模式正常驾驶超过150秒')
        if self.session is None or self.session.phase != Phase.DRIVING:
            self.probe_last = now
            return task.cont
        if not self.probe_driving:
            self.session.set_controller(ViewDriver(), bind_world=True)
            self.probe_driving = True
            self.probe_last = now
            self.probe_tick_start = self.session.current.tick
            return task.cont
        state = self.session.current
        distance = self.session.simulation.road.locate(state.player)[0]
        props = self.win.getProperties()
        self.probe_rows.append({'mode': self.probe_modes[self.probe_index].value,
            'wall_frame_ms': (now-self.probe_last)*1000, 'progress_m': distance, 'tick': state.tick,
            'foreground': props.getForeground(), 'minimized': props.getMinimized(),
            'dropped_time': self.session.stepper.dropped_time, 'after_capture': self.probe_after_capture})
        self.probe_last, self.probe_after_capture = now, False
        if distance >= 120 and not self.probe_captured:
            self.graphicsEngine.syncFrame()
            assert self.win.getScreenshot().write(Filename.fromOsSpecific(str(
                self.probe_output/(self.probe_modes[self.probe_index].value+'-120m.png'))))
            self.probe_captured, self.probe_after_capture = True, True
        if distance < 190:
            return task.cont
        rows = [row for row in self.probe_rows if row['mode'] == self.probe_modes[self.probe_index].value]
        usable = [row['wall_frame_ms'] for row in rows if not row['after_capture']]
        tick, dropped, monotonic = self.session.progress()
        report = {'mode': self.probe_modes[self.probe_index].value, 'frames': len(rows),
            'foreground': sum(row['foreground'] for row in rows), 'minimized': sum(row['minimized'] for row in rows),
            'frame_ms': {'median': float(np.median(usable)), 'p95': float(np.percentile(usable, 95)),
                         'max': max(usable), 'over_33ms': sum(value>1000/30 for value in usable)},
            'owner_end': [tick, dropped, monotonic], 'tick_start': self.probe_tick_start,
            'config': asdict(self.session.simulation.config), 'last': asdict(state),
            'checkpoint_visible': sum(not node.isHidden() for node in self.scene.checkpoint_nodes)}
        self.probe_runs.append(report)
        print('COAST MODE', report['mode'], report['frames'], report['frame_ms'], flush=True)
        assert state.collisions == 0 and dropped == 0
        if self.probe_index == 0:
            self.probe_index = 1
            self.probe_driving = self.probe_captured = False
            self.back_to_menu()
            self.taskMgr.doMethodLater(.5, self.begin_mode, 'coast-next')
            return task.cont
        assert self.probe_runs[0]['config'] == report['config']
        self.write_report(True)
        self.userExit()
        return task.done

    def write_report(self, completed):
        (self.probe_output/'frames.json').write_text(json.dumps(self.probe_rows, indent=2)+'\n', encoding='utf-8')
        report = {'completed': completed, 'runs': self.probe_runs,
                  'scope': '1280x720默认Draw/独立120Hz，各从静止正常循线190m；原Controller经过Control执行，未人工驾驶。',
                  'limits': '用户实验台预览可能仍开，非单实例比较/长期60FPS或全步Gate；截图后帧单列。',
                  'model_fingerprints': model_fingerprint()}
        (self.probe_output/'summary.json').write_text(json.dumps(report, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')


if __name__ == '__main__':
    multiprocessing.freeze_support()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    arguments = parser.parse_args()
    output = arguments.output.resolve()
    output.mkdir(parents=True, exist_ok=False)
    os.environ['LOCALAPPDATA'] = str(output/'user')
    app = CoastalProbe(output)
    try:
        app.run()
    finally:
        if not (output/'summary.json').is_file():
            app.write_report(False)
        app.close_game()
