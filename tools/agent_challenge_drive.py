"""代理可见窗口实跑；沿正常预算入口与Control接口，不写玩家成绩。"""

import argparse
import json
import multiprocessing
import os
import sys
import time
from dataclasses import asdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT/'src'), str(ROOT/'tools'), str(ROOT/'tools/environment')]

from challenge_balance_check import BUILDS, RoadPilot
from local_kcd_drive import LocalVegetation
from panda3d.core import Filename, WindowProperties

from application import CoastalDrive
from challenge_build import BuildDraft
from challenge_catalog import SPRINT_CHALLENGES
from driving_modes import DrivingMode
from race import GameMode
from session import Phase


class VisibleDriver:
    def __init__(self, mode, target_kph):
        self.mode, self.target_kph = mode, target_kph

    def bind(self, simulation):
        self.pilot = RoadPilot(simulation, self.mode, target_kph=self.target_kph,
                               curve_acceleration=3.8)

    def sample(self, state, dt):
        return self.pilot.sample(state, dt)


class VisibleDrive(CoastalDrive):
    def __init__(self, output, mode, build, runs, target_kph):
        self.agent_output, self.agent_mode, self.agent_build = output, mode, build
        self.agent_runs, self.agent_target = runs, target_kph
        self.agent_started, self.agent_bound = False, False
        self.agent_results, self.agent_frames, self.agent_captures = [], [], []
        self.agent_next, self.agent_last = None, time.perf_counter()
        super().__init__(driving_mode=DrivingMode.GAME, abs_enabled=True, tcs_enabled=True, esc_enabled=True,
                         output=output/'runtime')
        properties = WindowProperties()
        properties.setTitle('CoastalDrive · 代理实跑（独立记录）')
        self.win.requestProperties(properties)
        self.taskMgr.add(self.agent_frame, 'agent-drive-observation', sort=99)

    def agent_frame(self, task):
        now = time.perf_counter()
        elapsed, self.agent_last = now-self.agent_last, now
        if not self.agent_started:
            if self._workspace_steps is not None:
                return task.cont
            self.start_sprint(self.agent_mode)
            self.budget_drafts[self.agent_mode] = self.agent_build
            self.career_panel.update_challenge(self.agent_build)
            self.challenge_action('challenge-start')
            self.agent_started = True
            return task.cont
        if self.session.phase == Phase.DRIVING and not self.agent_bound:
            self.session.set_controller(VisibleDriver(self.agent_mode, self.agent_target), bind_world=True)
            self.agent_bound = True
        if self.agent_bound and self.session.phase == Phase.DRIVING:
            status = self.session.highway.snapshot.engineering
            self.agent_frames.append({'frame_ms': elapsed*1000, 'tick': self.session.current.tick,
                'progress_m': status.progress_m, 'speed_kph': self.session.current.player.speed*3.6,
                'backlog_s': self.session.stepper.backlog_time,
                'foreground': self.win.getProperties().getForeground()})
            key = len(self.agent_results)+1, len(status.splits)
            if key not in self.agent_captures:
                self.agent_capture(f'run-{key[0]}-gate-{key[1]}')
                self.agent_captures.append(key)
            if self.agent_mode == GameMode.RIDGE_SPRINT:
                for distance in (435, 790, 980):
                    marker = len(self.agent_results)+1, distance
                    if status.progress_m >= distance and marker not in self.agent_captures:
                        self.agent_capture(f'run-{marker[0]}-approach-{distance}m')
                        self.agent_captures.append(marker)
        if self.agent_bound and self.session.phase == Phase.RESULTS and self.agent_next is None:
            status = self.session.highway.snapshot.engineering
            self.agent_results.append(asdict(status))
            self.agent_capture(f'run-{len(self.agent_results)}-result')
            self.agent_save()
            self.agent_next = now+6
            if len(self.agent_results) >= self.agent_runs:
                print(json.dumps({'finished': True, 'runs': len(self.agent_results)}), flush=True)
        if self.agent_next is not None and now >= self.agent_next and len(self.agent_results) < self.agent_runs:
            self.challenge_action('challenge-retry')
            self.agent_bound, self.agent_next = False, None
        return task.cont

    def agent_capture(self, name):
        path = self.agent_output/(name+'.png')
        if not self.win.saveScreenshot(Filename.fromOsSpecific(str(path))):
            raise OSError('实跑截图未保存：'+str(path))

    def agent_save(self):
        (self.agent_output/'summary.json').write_text(json.dumps({
            'agent_operated': True, 'controller': 'VisibleDriver/RoadPilot',
            'real_time_visible_window': True, 'mode': self.agent_mode.value,
            'build': asdict(self.agent_build), 'target_kph': self.agent_target,
            'results': self.agent_results, 'frames': self.agent_frames,
        }, ensure_ascii=False, indent=2), encoding='utf-8')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--route', choices=('bend_sprint', 'ridge_sprint'), default='bend_sprint')
    parser.add_argument('--build', choices=('stock', 'front-tire130', 'efficiency-ui'), default='front-tire130')
    parser.add_argument('--runs', type=int, default=2)
    parser.add_argument('--target-kph', type=float, default=105.)
    args = parser.parse_args()
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=False)
    os.environ['LOCALAPPDATA'] = str(output/'user')
    profile = LocalVegetation(output/'assets', ROOT/'logs/local-kcd-original-environment')
    profile.install()
    app = None
    try:
        base = SPRINT_CHALLENGES[GameMode(args.route)].base_config
        build = (BuildDraft(mass=.96, drag=round(.652/(base.drag_coefficient*base.frontal_area), 10)) if args.build == 'efficiency-ui'
                 else BUILDS[args.build])
        app = VisibleDrive(output, GameMode(args.route), build, args.runs, args.target_kph)
        app.run()
    finally:
        if app is not None:
            app.agent_save()
            app.close_game()
        profile.restore()


if __name__ == '__main__':
    multiprocessing.freeze_support()
    main()
