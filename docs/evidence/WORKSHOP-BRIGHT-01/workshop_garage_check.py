"""隔离采集工坊真实车模/预览/安装/返回；不生成虚构驾驶成绩。"""

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
from slalom_driver import SlalomDriver, apply_keys

from application import CoastalDrive
from race import GameMode
from session import Phase
from slalom_lesson import SlalomLesson, SlalomScores
from vehicle_designs import vehicle_design
from vehicle_workspace import WorkspaceVehicle


def check(output, size, practice_run=False, practice_record=None, fast_only=False):
    output.mkdir(parents=True, exist_ok=False)
    os.environ['LOCALAPPDATA'] = str(output/'user-data')
    vehicle = WorkspaceVehicle('reference-rwd', vehicle_design('reference-rwd').config)
    app = CoastalDrive(smoke=True, output=output, lab_output=output/'reports', render_size=size,
                       workspace_vehicle=vehicle)
    app.taskMgr.remove('finish-smoke')
    app.taskMgr.remove('drive-update')
    images = []
    rows = []

    def capture(name):
        before = asdict(app.session.current)
        app.main_menu.resize(app.getAspectRatio())
        app.hud.resize(app.getAspectRatio())
        app.lab_return_button.setX(app.getAspectRatio()-.44)
        app.ghost_button.setX(app.getAspectRatio()-.44)
        if app.session.phase in (Phase.DRIVING, Phase.COUNTDOWN):
            app._shown_phase = None
            app.refresh_panel()
        if app.scene is not None:
            app.chase_camera.position = None
            app.apply_scene(app.session.current, 0.)
            app.hud.update(app.session.current, app.session.race.snapshot, app.session.highway.snapshot,
                           track=app.session.simulation.track, countdown='', notice='')
        for _ in range(6):
            app.taskMgr.step()
        app.graphicsEngine.syncFrame()
        assert app.win.getScreenshot().write(Filename.fromOsSpecific(str(output/(name+'.png'))))
        assert asdict(app.session.current) == before
        images.append(name)

    try:
        if fast_only:
            app.back_to_menu()
            app.workshop_garage_return = True
            app.choose_highway()
            capture('12-trial-selection')
            app.choose_slalom_lesson(GameMode.FAST_SLALOM)
            capture('10-fast-rules')
            app.start_slalom_lesson()
            for _ in range(360):
                app.session.tick()
            assert app.session.phase == Phase.DRIVING
            capture('11-fast-guide')
            summary = {'passed': True, 'size': size, 'captures': images, 'new_driving_steps': 0,
                       'scope': '真实规则页与静止起步的实时速度带；只执行倒计时，无新道路驾驶'}
            (output/'summary.json').write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding='utf-8')
            return summary
        app.open_workshop_garage()
        capture('01-garage')
        app.workshop_garage.activate(0)
        assert app.slalom_mode == GameMode.SLALOM_PRACTICE
        capture('02-front-wheels')
        app.tire_tuning.activate(3)
        assert app.workspace_vehicle == vehicle
        capture('03-front-preview')
        app.tire_tuning.activate(6)
        assert not app.workshop_garage.root.isHidden()
        if practice_run:
            app.workshop_garage.activate(0)
            app.tire_tuning.activate(8)
            for _ in range(360):
                app.session.tick()
            driver = SlalomDriver(35., app.session.vehicle_config,
                                  origin=app.session.highway.snapshot.slalom.start_progress, straight=True)
            for _ in range(4802):
                apply_keys(app.session.keyboard, driver.sample(app.session.current, 1/120))
                app.session.tick()
                result = app.session.highway.snapshot.slalom
                rows.append({'snapshot': asdict(app.session.current), 'result': asdict(result)})
                if len(result.clearances) == 1 and len(rows[-2]['result']['clearances']) == 0:
                    capture('08-missed-gate-continues')
                if app.session.phase == Phase.RESULTS:
                    break
            assert result.succeeded and result.gates == 1 and not result.medal
            app._shown_phase = None
            app.refresh_panel()
            capture('09-practice-finished')
            with gzip.open(output/'practice-raw.json.gz', 'wt', encoding='utf-8') as stream:
                json.dump(rows, stream, ensure_ascii=False)
            app.buttons[1]['command']()
        app.workshop_garage.activate(1)
        capture('04-brakes')
        app.tire_tuning.activate(3)
        app.tire_tuning.activate(4)
        assert app.workspace_vehicle.config.front_brake_share == .8
        capture('05-brakes-installed')
        app.tire_tuning.activate(5)
        assert app.workspace_vehicle == vehicle
        app.tire_tuning.activate(8)
        assert app.session.phase == Phase.COUNTDOWN and app.session.mode == GameMode.SHORT_BRAKING
        for _ in range(360):
            app.session.tick()
        app.session.finish()
        app._shown_phase = None
        app.refresh_panel()
        capture('06-ended-trial')
        app.buttons[1]['command']()
        assert not app.workshop_garage.root.isHidden()
        capture('07-returned-garage')
        if practice_record is not None:
            with gzip.open(practice_record, 'rt', encoding='utf-8') as stream:
                previous = json.load(stream)
            run = SlalomLesson(previous[0]['result']['start_progress'],
                               SlalomScores(output/'recheck-practice.json', 'practice'), vehicle.config,
                               practice=True)
            elapsed = 0.
            for row in previous:
                elapsed += 1/120
                result = run.update(row['result']['start_progress']+row['result']['position'],
                    row['snapshot']['player']['velocity'][1], elapsed,
                    lateral=row['snapshot']['player']['position'][0],
                    heading=row['snapshot']['player']['heading'], collisions=row['snapshot']['collisions'])
                assert json.loads(json.dumps(asdict(result))) == row['result']
            app.session.mode = GameMode.SLALOM_PRACTICE
            app.session.race.start(GameMode.SLALOM_PRACTICE)
            app.session.phase = Phase.RESULTS
            app.session.highway.snapshot = replace(app.session.highway.snapshot, challenge=True,
                finished=True, running=False, succeeded=True, slalom=result)
            app._shown_phase = None
            app.refresh_panel()
            capture('09-practice-finished')
            app.buttons[1]['command']()
        summary = {'passed': True, 'size': size, 'captures': images, 'vehicle_restored': True,
                   'render_snapshot_unchanged': True, 'new_driving_steps': len(rows),
                   'reused_practice_steps': len(previous) if practice_record is not None else 0,
                   'scope': '真实UI/车模/安装恢复/同题起步与返回；可选低速直行完整练习，无正式成功成绩',
                   'human_gate': 'pending'}
        (output/'summary.json').write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding='utf-8')
        return summary
    finally:
        app.close_game()


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--size', nargs=2, type=int, default=(1280, 720))
    parser.add_argument('--practice-run', action='store_true')
    parser.add_argument('--practice-record', type=Path)
    parser.add_argument('--fast-guide-only', action='store_true')
    args = parser.parse_args()
    print(json.dumps(check(args.output.resolve(), tuple(args.size), args.practice_run,
                           args.practice_record, args.fast_guide_only), ensure_ascii=False))
