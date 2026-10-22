"""采集独立生涯页面，并实际完成入门赛事、领奖和购买安装；不读写用户存档。"""

import argparse
import gzip
import json
import os
import sys
from dataclasses import asdict, replace
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'src'))

from career_check import CareerDriver
from panda3d.core import Filename
from slalom_driver import apply_keys

from application import CoastalDrive
from career import CareerProgress
from career_run import CareerRun
from session import Phase
from vehicle_designs import vehicle_design
from vehicle_workspace import WorkspaceVehicle


def check(output, size, reuse=None):
    output.mkdir(parents=True, exist_ok=False)
    os.environ['LOCALAPPDATA'] = str(output/'isolated-user')
    app = CoastalDrive(smoke=True, output=output, render_size=size,
                       workspace_vehicle=WorkspaceVehicle('reference-rwd', vehicle_design('reference-rwd').config))
    app.taskMgr.remove('finish-smoke')
    app.taskMgr.remove('drive-update')
    images, cases = [], []

    def capture(name):
        before = asdict(app.session.current)
        app.main_menu.resize(app.getAspectRatio())
        app.hud.resize(app.getAspectRatio())
        app.lab_return_button.setX(app.getAspectRatio()-.44)
        if app.session.phase in (Phase.DRIVING, Phase.COUNTDOWN):
            app.apply_scene(app.session.current, 0.)
            app.hud.update(app.session.current, app.session.race.snapshot, app.session.highway.snapshot,
                track=app.session.simulation.track, countdown='', notice='', driving_mode=app.session.driving_mode)
        for _ in range(5):
            app.taskMgr.step()
        app.graphicsEngine.syncFrame()
        app.win.getScreenshot().write(Filename.fromOsSpecific(str(output/(name+'.png'))))
        assert before == asdict(app.session.current)
        images.append(name)

    try:
        app.main_menu.actions[2]()
        assert app.career_panel.page == 'board'
        capture('01-events')
        app.career_action('brief', 'first-drive')
        capture('02-first-brief')
        app.career_action('brief', 'parking')
        capture('03-parking-brief')
        app.career_action('brief', 'coastal-cup')
        capture('04-locked-cup')
        app.career_action('garage')
        capture('05-garage-locked')
        for event_id in ('first-drive', 'parking'):
            app.career_action('board')
            app.career_action('brief', event_id)
            app.career_action('start', event_id)
            for _ in range(360):
                app.session.tick()
            app._shown_phase = None
            app.refresh_panel()
            capture('12-driving-hud' if event_id == 'first-drive' else '14-parking-hud')
            if event_id == 'first-drive':
                app.session.pause()
                app._shown_phase = None
                app.refresh_panel()
                capture('13-pause')
                app.career_action('resume')
            driver = CareerDriver(app.session, app.session.highway.career.event)
            if reuse is not None:
                with gzip.open(reuse/(event_id+'.json.gz'), 'rt', encoding='utf-8') as stream:
                    rows = json.load(stream)
                run = CareerRun(event_id, rows[0]['result']['start_progress'], app.session.vehicle_config)
                for row in rows:
                    result = run.update(row['progress'], row['result']['elapsed'], lateral=row['lateral'],
                        heading=row['heading'], speed=abs(row['speed']), collisions=row['collisions'], reset=False)
                    assert json.loads(json.dumps(asdict(result))) == row['result'], (event_id, row['tick'])
                app.session.highway.snapshot = replace(app.session.highway.snapshot, career=result,
                    finished=True, succeeded=result.succeeded, running=False)
                app.session.phase = Phase.RESULTS
            else:
                rows = []
                while app.session.phase == Phase.DRIVING:
                    apply_keys(app.session.keyboard, driver.sample())
                    app.session.tick()
                    rows.append({'tick': app.session.current.tick,
                                 'keys': sorted(app.session.keyboard.pressed),
                                 'result': asdict(app.session.highway.snapshot.career)})
            result = app.session.highway.snapshot.career
            assert result.succeeded
            app._shown_phase = None
            app.refresh_panel()
            capture('06-reward' if event_id == 'first-drive' else '08-parking-reward')
            cases.append({'event': event_id, 'steps': len(rows), 'result': asdict(result)})
            if reuse is None:
                (output/(event_id+'-ui-run.json')).write_text(json.dumps(rows, ensure_ascii=False), encoding='utf-8')
            if event_id == 'first-drive':
                app.career_action('board')
                capture('07-unlocked-events')
        app.career_action('garage')
        capture('09-shop')
        before = app.workspace_vehicle
        app.career_action('part', 'sport-front')
        assert app.workspace_vehicle.config.lateral_stiffness == 70000.
        capture('10-installed')
        owned, credits = set(app.career_progress.owned), app.career_progress.credits
        app.career_action('restore')
        assert app.workspace_vehicle == before
        app.career_action('part', 'sport-front')
        assert app.career_progress.owned == owned and app.career_progress.credits == credits
        restored = CareerProgress(app.career_progress.path)
        assert restored.records == app.career_progress.records and restored.owned == owned
        app.career_action('board')
        capture('11-progress-after-reload')
        steps = sum(c['steps'] for c in cases)
        summary = {'passed': True, 'captures': images, 'size': size, 'new_driving_steps': steps if reuse is None else 0,
                   'reused_driving_steps': steps if reuse is not None else 0,
                   'cases': cases, 'stars': restored.stars, 'credits': restored.credits,
                   'owned': sorted(restored.owned), 'source': str(reuse) if reuse is not None else None,
                   'scope': ('真实UI/复核复用旧入门两赛/领奖复载购买安装恢复；新道路驾驶0，非人工试玩' if reuse is not None else
                             '真实UI/实际入门两赛/领奖复载购买安装恢复；非人工试玩')}
        (output/'summary.json').write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding='utf-8')
        return summary
    finally:
        app.close_game()


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--size', nargs=2, type=int, default=(1280, 720))
    parser.add_argument('--reuse', type=Path)
    args = parser.parse_args()
    print(json.dumps(check(args.output.resolve(), tuple(args.size), args.reuse), ensure_ascii=False))
