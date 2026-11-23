"""从正常高速入口持续驾驶到城市段；保留原车、120Hz、交通和完整墙钟记录。"""

import argparse
import gc
import hashlib
import json
import multiprocessing
import os
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT/'src'), str(ROOT/'tools/environment'), str(Path(__file__).resolve().parent)]

from check_coastal_stalls import capture_authority
from check_driving_composition import ViewDriver
from check_post_impact_window import ImpactProbe
from local_kcd_drive import LocalVegetation
from panda3d.core import Filename, WindowProperties

import session_process
from session import Phase
from vehicle_workspace import WorkspaceVehicle


class HighwayDriveProbe(ImpactProbe):
    def __init__(self, output, vehicle, distance, density):
        self.target_distance = distance
        self.target_density = density
        self.entry_states = []
        self.visual_sources = {name: hashlib.sha256((ROOT/name).read_bytes()).hexdigest()
            for name in ('src/environment/expressway_city.py', 'src/environment/expressway_buildings.py',
                         'src/environment/expressway_route.py', 'src/environment/expressway_materials.py',
                         'src/environment/expressway.py', 'src/scene.py',
                         'assets/game/expressway/shaders/city-plaster.glsl',
                         'tools/environment/local_kcd_drive.py', 'tools/environment/local_coastal_landscape.py')}
        super().__init__(output, vehicle, (2509, 1180), region='highway')
        properties = WindowProperties()
        properties.setTitle('CoastalDrive · 高速城市段驾驶复测')
        self.win.requestProperties(properties)

    def begin_mode(self, task):
        self.highway_density_index = self.highway_density_keys.index(self.target_density)
        return super().begin_mode(task)

    def check_frame(self, task):
        now = time.perf_counter()
        properties = self.win.getProperties()
        phase = None if self.session is None else self.session.phase.value
        observation = (phase, properties.getForeground(), properties.getMinimized(),
                       self._workspace_steps is not None)
        if not self.entry_states or tuple(self.entry_states[-1]['state']) != observation:
            self.entry_states.append({'wall_s': now-self.probe_started, 'state': observation})
            (self.probe_output/'entry-states.json').write_text(
                json.dumps(self.entry_states, ensure_ascii=False, indent=2), encoding='utf-8')
            print('ENTRY STATE', self.entry_states[-1], flush=True)
        if now-self.probe_started > 600:
            raise TimeoutError('正常高速行驶未在600墙钟秒内到达目标')
        if self.session is None or self.session.phase != Phase.DRIVING:
            self.probe_last = now
            return task.cont
        if not self.probe_driving:
            self.session.set_controller(ViewDriver(), bind_world=True)
            self.probe_driving = True
            self.probe_last = now
            return task.cont
        state = self.session.current
        distance = self.session.simulation.road.locate(state.player)[0]
        self.probe_rows.append({'mode': self.session.mode.value, 'phase': self.session.phase.value,
            'wall_frame_ms': (now-self.probe_last)*1000, 'progress_m': distance,
            'tick': state.tick, 'simulation_time': state.time, 'collisions': state.collisions,
            'foreground': properties.getForeground(), 'minimized': properties.getMinimized(),
            'size': [self.win.getXSize(), self.win.getYSize()], 'after_capture': False,
            'dropped_time': self.session.stepper.dropped_time})
        self.probe_last = now
        self.attach_phases()
        self.probe_rows[-1]['streaming'] = dict(self.scene.segment_work)
        if distance < self.target_distance:
            return task.cont
        self.write_report(True)
        # 截图在计时结束后取得，不从正常驾驶样本中挑删截图造成的长帧。
        self.graphicsEngine.syncFrame()
        assert self.win.getScreenshot().write(Filename.fromOsSpecific(str(self.probe_output/'finish.png')))
        self.userExit()
        return task.done

    def write_report(self, completed):
        self.attach_phases()
        rows = self.probe_rows
        values = sorted(row['wall_frame_ms'] for row in rows)
        report = {'completed': completed, 'target_m': self.target_distance, 'density': self.target_density,
            'scope': '正常菜单/原车/原大窗口/12或18交通/独立120Hz；循线Controller不模拟键盘，不改运行姿态。',
            'all_foreground': bool(rows) and all(row['foreground'] and not row['minimized'] for row in rows),
            'last_distance': rows[-1]['progress_m'] if rows else None,
            'collisions': rows[-1]['collisions'] if rows else None,
            'dropped_time': rows[-1]['dropped_time'] if rows else None,
            'max_backlog_ms': max((row['authority_backlog_ms'] for row in rows), default=None),
            'frame_ms': {str(percent): values[round((len(values)-1)*percent/100)]
                         for percent in (50, 95, 99, 100)} if values else {},
            'over_33ms': sum(value > 1000/30 for value in values),
            'over_50ms': sum(value > 50 for value in values),
            'traffic_models': self.session.simulation.traffic_models,
            'entry_states': self.entry_states,
            'final_phase': self.session.phase.value,
            'visual_sources': self.visual_sources,
            'limits': '自动控制实际驾驶，不替代人工观感、其它入口或长期验收。'}
        (self.probe_output/'summary.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
        (self.probe_output/'frames.json').write_text(json.dumps(rows), encoding='utf-8')


if __name__ == '__main__':
    multiprocessing.freeze_support()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--workspace', type=Path, required=True)
    parser.add_argument('--distance', type=int, choices=(900, 4200), default=4200)
    parser.add_argument('--density', choices=('normal', 'busy'), default='normal')
    args = parser.parse_args()
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=False)
    vehicle = WorkspaceVehicle.load(args.workspace.resolve())
    if vehicle is None:
        raise FileNotFoundError(args.workspace)
    os.environ['LOCALAPPDATA'] = str(output/'user')
    os.environ['COASTAL_STALL_CAPTURE'] = str(output)
    local = LocalVegetation(ROOT/'logs/local-kcd-drive/assets', ROOT/'logs/local-kcd-original-environment')
    local.install()
    session_process._serve = capture_authority
    app = HighwayDriveProbe(output, vehicle, args.distance, args.density)
    try:
        app.run()
    finally:
        if not (output/'summary.json').is_file():
            app.write_report(False)
            app.graphicsEngine.syncFrame()
            assert app.win.getScreenshot().write(Filename.fromOsSpecific(str(output/'incomplete.png')))
        gc.callbacks.remove(app.record_gc)
        app.close_game()
        local.restore()
