"""采集生涯HUD两画幅，另可实跑一次正常400米及暂停/结算闭环。"""

import argparse
import gzip
import json
import os
import sys
from dataclasses import asdict, replace
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'src'))

from panda3d.core import Filename

from application import CoastalDrive
from career_run import CareerResult
from driving_modes import DrivingMode
from session import Phase
from vehicle_designs import vehicle_design
from vehicle_workspace import WorkspaceVehicle


def check(output, size, drive, replay_result):
    output.mkdir(parents=True, exist_ok=False)
    os.environ['LOCALAPPDATA'] = str(output/'user')
    app = CoastalDrive(smoke=True, output=output, render_size=size,
        workspace_vehicle=WorkspaceVehicle('gr86-2022-premium-6mt', vehicle_design('gr86-2022-premium-6mt').config))
    app.taskMgr.remove('finish-smoke')
    app.taskMgr.remove('drive-update')
    captures, rows = [], []

    def shot(name, *, result=None, mode=None):
        before, simulation = app.session.current, app.session.simulation
        if app.session.phase in (Phase.DRIVING, Phase.COUNTDOWN, Phase.PAUSED, Phase.RESULTS):
            # 离屏稀疏采样没有连续相机帧，取景时直接对准当前快照，不移动物理车辆。
            app.chase_camera.position = None
            app.apply_scene(before, 0.)
        app.hud.resize(app.getAspectRatio())
        highway = app.session.highway.snapshot
        state = before
        if result is not None:
            highway = replace(highway, career=result)
            speed = 25/3.6 if result.event_id == 'first-drive' else 0. if result.event_id == 'parking' else 45/3.6
            state = replace(before, player=replace(before.player, speed=speed, gear=1, rpm=3467.))
        app.hud.update(state, app.session.race.snapshot, highway, track='endless', countdown='', notice='',
            driving_mode=mode or app.session.driving_mode)
        app.refresh_panel()
        for _ in range(6):
            app.taskMgr.step()
        app.graphicsEngine.syncFrame()
        app.win.getScreenshot().write(Filename.fromOsSpecific(str(output/(name+'.png'))))
        assert app.session.current == before and app.session.simulation is simulation
        captures.append({'image': name+'.png', 'fixture': result is not None,
                         'result': None if highway.career is None else asdict(highway.career)})

    try:
        app.open_career()
        app.career_action('start', 'first-drive')
        # 倒计时使用正式会话入口；图像采集不额外推进权威世界。
        while app.session.phase == Phase.COUNTDOWN:
            app.session.tick()
        first = CareerResult('first-drive', 8., position=4.8, elapsed=2.)
        shot('01-sprint-layout', result=first)
        windows = app.graphicsEngine.getNumWindows()
        shot('02-parking-layout', result=CareerResult('parking', 8., position=197.5, elapsed=17.3, stopping_ticks=24))
        shot('03-slalom-layout', result=CareerResult('slalom', 8., position=300., elapsed=25., passed=(True, False, True)))
        shot('04-simulation-controls', result=first, mode=DrivingMode.SIMULATION)
        assert app.graphicsEngine.getNumWindows() == windows
        assert app.career_progress.stars == 0 and not app.career_progress.path.exists()
        result = None
        if drive:
            app.session.keyboard.press('w')
            for step in range(7200):
                app.session.tick()
                result = app.session.highway.snapshot.career
                rows.append({'state': asdict(app.session.current), 'result': asdict(result),
                             'keys': sorted(app.session.keyboard.pressed)})
                if step in (239, 899):
                    shot(f'05-actual-drive-{step+1}')
                if step == 899:
                    before, simulation = app.session.current, app.session.simulation
                    app.hud.career.pause['command'](*app.hud.career.pause['extraArgs'])
                    assert app.session.phase == Phase.PAUSED and app.career_panel.page == 'pause'
                    shot('06-actual-pause')
                    assert app.session.simulation is simulation and app.session.current == before
                    app.career_action('resume')
                    assert app.session.phase == Phase.DRIVING and app.session.current == before
                    app.session.keyboard.press('w')
                if app.session.phase == Phase.RESULTS:
                    break
            app.session.keyboard.clear()
            assert result.succeeded and result.stars == 3
            app._shown_phase = None
            shot('07-actual-result')
            assert app.career_progress.credits == 300 and app.career_progress.stars == 3
            with gzip.open(output/'actual-drive.json.gz', 'wt', encoding='utf-8') as stream:
                json.dump(rows, stream, ensure_ascii=False)
            app.career_action('garage')
            shot('08-actual-garage-return')
            app.career_action('garage-back')
            shot('09-actual-brief-return')
            assert app.career_panel.page == 'brief' and app.career_panel.event_id == 'first-drive'
        if replay_result is not None:
            with gzip.open(replay_result, 'rt', encoding='utf-8') as stream:
                recorded = json.load(stream)
            result = CareerResult(**recorded[-1]['result'])
            assert result.finished and result.succeeded and result.stars == 3
            app.open_career()
            award = app.career_progress.record(result)
            app.career_panel.show_result(app.career_progress, result, award)
            shot('07-recorded-result')
            app.career_action('garage')
            shot('08-recorded-garage-return')
            app.career_action('garage-back')
            shot('09-recorded-brief-return')
            assert app.career_panel.page == 'brief' and app.career_panel.event_id == 'first-drive'
        report = {'passed': True, 'size': size, 'captures': captures, 'new_driving_steps': len(rows),
            'result': None if result is None else asdict(result), 'display_worlds': 0,
            'reused_actual_run': str(replay_result) if replay_result is not None else None,
            'windows_after_first_draw': windows, 'windows_after_navigation': app.graphicsEngine.getNumWindows(),
            'scope': '前四图为只读HUD夹具；可选一次真实GR86全油门400米，或只读回放已保存的实际完赛数据制作领奖/车库往返页面；采图只对准当前快照，不推进物理，不替代人工审美或完整阶段性能'}
        (output/'summary.json').write_text(json.dumps(report, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
        print(json.dumps({'passed': True, 'size': size, 'captures': len(captures),
                          'new_driving_steps': len(rows)}, ensure_ascii=False))
    finally:
        app.close_game()


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', required=True, type=Path)
    parser.add_argument('--size', nargs=2, type=int, default=(1280, 720))
    parser.add_argument('--drive', action='store_true')
    parser.add_argument('--replay-result', type=Path)
    args = parser.parse_args()
    if args.drive and args.replay_result is not None:
        parser.error('--drive与--replay-result择一使用')
    check(args.output.resolve(), tuple(args.size), args.drive, args.replay_result)
