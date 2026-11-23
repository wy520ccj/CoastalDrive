"""正常窗口加载阶段的主循环/工作阶段间隔；不更改加载路径，不作驾驶帧率Gate。"""

import argparse
import importlib.util
import json
import multiprocessing
import sys
import time
from dataclasses import asdict
from pathlib import Path

from direct.showbase.ShowBase import ShowBase
from panda3d.core import Filename

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT/'tools/environment'))

import check_interactive_local_drive as probe
import local_coastal_landscape

from session import Phase


class LoadingProbe(probe.DrivingProbe):
    def __init__(self, *args, **kwargs):
        self.loading_phases, self.loading_frames = [], []
        super().__init__(*args, **kwargs)
        self.loading_previous = self.loading_window_opened_at
        self.loading_constructor_ms = (time.perf_counter()-self.loading_window_opened_at)*1000

    def _advance_workspace(self, task):
        start = time.perf_counter()
        result = super()._advance_workspace(task)
        self.loading_phases.append({'started_at': start, 'wall_ms': (time.perf_counter()-start)*1000,
                                    'stage': self.workspace_loading.stage.getText()})
        return result

    def sync_scene(self, **kwargs):
        start = time.perf_counter()
        result = super().sync_scene(**kwargs)
        self.loading_phases.append({'started_at': start, 'wall_ms': (time.perf_counter()-start)*1000,
                                    'stage': 'scene-sync'})
        return result

    def _enter_game_steps(self, *args, **kwargs):
        original = self.session.start

        def started_session(*values, **options):
            start = time.perf_counter()
            result = original(*values, **options)
            self.loading_phases.append({'started_at': start, 'wall_ms': (time.perf_counter()-start)*1000,
                                        'stage': 'session-start'})
            return result

        self.session.start = started_session
        try:
            yield from super()._enter_game_steps(*args, **kwargs)
        finally:
            self.session.start = original

    def probe_frame(self, task):
        now = time.perf_counter()
        self.loading_frames.append({'finished_at': now, 'wall_ms': (now-self.loading_previous)*1000,
                                    'workspace': self.workspace,
                                    'loading': self._workspace_steps is not None,
                                    'phase': self.session.phase.value})
        self.loading_previous = now
        if now-self.probe_started > 120:
            raise TimeoutError('正常窗口加载检查超过120秒')
        if (self.probe_requested is not None and self._workspace_steps is None
                and self.workspace == 'game' and self.session.phase in (Phase.COUNTDOWN, Phase.DRIVING, Phase.PAUSED)):
            self.graphicsEngine.syncFrame()
            self.win.getScreenshot().write(Filename.fromOsSpecific(str(self.probe_output/'ready.png')))
            report = {'scope': '正常独立会话/Draw/原入口加载路径；保留先前暂停的试玩窗，非单实例FPS样本。主循环间隔不等同Windows系统的无响应判定。',
                      'constructor_after_window_ms': self.loading_constructor_ms,
                      'entry_to_ready_s': now-self.probe_requested,
                      'max_main_frame_gap_ms': max(row['wall_ms'] for row in self.loading_frames),
                      'max_loading_step_ms': max(row['wall_ms'] for row in self.loading_phases),
                      'frames': self.loading_frames, 'loading_steps': self.loading_phases,
                      'owner_progress': self.session.progress(),
                      'vehicle_config': asdict(self.session.simulation.config), 'entry_only': True}
            (self.probe_output/'summary.json').write_text(json.dumps(report, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
            print('LOADING READY', {key: report[key] for key in (
                'constructor_after_window_ms', 'entry_to_ready_s', 'max_main_frame_gap_ms', 'max_loading_step_ms')}, flush=True)
            self.userExit()
            return task.done
        return task.cont


def check(output, legacy):
    original_init = ShowBase.__init__
    original_rocks = local_coastal_landscape.load_rocks

    def initialized(app, *args, **kwargs):
        original_init(app, *args, **kwargs)
        app.loading_window_opened_at = time.perf_counter()

    if legacy is not None:
        spec = importlib.util.spec_from_file_location('loading_rocks_baseline', legacy)
        baseline = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(baseline)
        local_coastal_landscape.load_rocks = baseline.load_rocks
    ShowBase.__init__ = initialized
    probe.DrivingProbe = LoadingProbe
    try:
        probe.check(output, False, False)
        report = json.loads((output/'summary.json').read_text(encoding='utf-8'))
        report.update(target_distance=None, legacy_rock_loader=legacy is not None)
        (output/'summary.json').write_text(json.dumps(report, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
    finally:
        ShowBase.__init__ = original_init
        local_coastal_landscape.load_rocks = original_rocks


if __name__ == '__main__':
    multiprocessing.freeze_support()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--legacy-rock-loader', type=Path)
    args = parser.parse_args()
    check(args.output.resolve(), args.legacy_rock_loader)
