"""隔离进度下从车库购件、换车复载、真实开赛到逐次恢复，并采集实际界面。"""

import argparse
import gzip
import json
import os
import sys
from dataclasses import asdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'src'))

from panda3d.core import Filename

from application import CoastalDrive
from career import EVENTS, PART_BY_ID
from career_run import CareerResult
from career_tuning import installed_parts
from session import Phase
from vehicle_designs import vehicle_design
from vehicle_workspace import WorkspaceVehicle


def check(output, size):
    output.mkdir(parents=True, exist_ok=False)
    os.environ['LOCALAPPDATA'] = str(output/'user')
    original = WorkspaceVehicle('game-tuned', vehicle_design('game-tuned').config)
    app = CoastalDrive(smoke=True, output=output, render_size=size, workspace_vehicle=original)
    app.taskMgr.remove('finish-smoke')
    app.taskMgr.remove('drive-update')
    captures, rows = [], []

    def shot(name):
        before = app.session.current
        for _ in range(6):
            app.taskMgr.step()
        app.graphicsEngine.syncFrame()
        app.win.getScreenshot().write(Filename.fromOsSpecific(str(output/(name+'.png'))))
        assert app.session.current == before
        captures.append(name+'.png')

    try:
        app.open_career_collection()
        app.career_action('garage-tab', 'upgrade')
        for topic in ('power', 'suspension'):
            app.career_action('garage-topic', topic)
            shot('01-'+topic+'-locked')
        for event in EVENTS:
            app.career_progress.record(CareerResult(event.id, 8., elapsed=25., finished=True, succeeded=True, stars=3))
        versions = [original]
        windows = app.graphicsEngine.getNumWindows()
        for part_id in ('street-power', 'sport-suspension', 'sport-front', 'sport-brakes'):
            app.career_action('garage-topic', PART_BY_ID[part_id].topic)
            shot('02-'+part_id+'-offer')
            app.career_panel.select(app.career_panel.primary)
            app.career_panel.key('enter')
            versions.append(app.workspace_vehicle)
            assert app.session.base_vehicle_config == versions[-1].config
            shot('03-'+part_id+'-installed')
        assert app.career_progress.credits == 1010
        app.career_action('garage-car', 'coastal-hatch')
        app.career_action('garage-select')
        app.career_action('garage-car', 'game-tuned')
        app.career_action('garage-select')
        assert app.workspace_vehicle == WorkspaceVehicle.load(app.workspace_path) == versions[-1]
        for part_id in ('street-power', 'sport-suspension'):
            app.career_action('part', part_id)
        assert app.workspace_vehicle == versions[-1] and app.career_progress.credits == 1010
        assert installed_parts(app.workspace_vehicle) == {'street-power', 'sport-suspension'}
        assert app.graphicsEngine.getNumWindows() == windows
        shot('04-reloaded-mixed-parts')
        app.career_action('start', 'first-drive')
        while app.session.phase == Phase.COUNTDOWN:
            app.session.tick()
        assert app.session.vehicle_config.torque_curve == versions[-1].config.torque_curve
        assert app.session.vehicle_config.suspension_spring_rates == versions[-1].config.suspension_spring_rates
        app.session.keyboard.press('w')
        for _ in range(7200):
            app.session.tick()
            result = app.session.highway.snapshot.career
            rows.append({'state': asdict(app.session.current), 'keys': sorted(app.session.keyboard.pressed),
                         'control': asdict(app.session.last_control), 'result': asdict(result)})
            if app.session.phase == Phase.RESULTS:
                break
        app.session.keyboard.clear()
        assert result.succeeded and result.stars == 3
        app._shown_phase = None
        app.refresh_panel()
        assert app.career_award['credits'] == 0 and app.career_progress.credits == 1010
        shot('05-actual-upgraded-race-result')
        app.career_action('garage')
        for index, expected in enumerate(reversed(versions[:-1])):
            app.career_action('restore')
            assert app.workspace_vehicle == WorkspaceVehicle.load(app.workspace_path) == expected
            assert app.session.base_vehicle_config == expected.config
            shot('06-restore-'+str(index))
        assert app.workspace_vehicle == original
        app.career_action('garage-back')
        assert app.career_panel.page == 'brief' and app.career_panel.event_id == 'first-drive'
        shot('07-return-to-event')
        with gzip.open(output/'actual-drive.json.gz', 'wt', encoding='utf-8') as stream:
            json.dump(rows, stream, ensure_ascii=False)
        report = {'passed': True, 'size': size, 'captures': captures, 'new_driving_steps': len(rows),
            'result': asdict(result), 'upgraded_config': asdict(versions[-1].config), 'final_credits': 1010,
            'scope': '18星起始进度为隔离UI夹具；四类真实购买安装/混装/复载/重复不收费不叠加/完整恢复/键盘返回；实际升级车全油门完成400米，旧记录不重复领奖；截图不推进物理，不替代人工审美或趣味性'}
        (output/'summary.json').write_text(json.dumps(report, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
        print(json.dumps({'passed': True, 'captures': len(captures), 'new_driving_steps': len(rows),
                          'seconds': result.elapsed, 'stars': result.stars}, ensure_ascii=False))
    finally:
        app.close_game()


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', required=True, type=Path)
    parser.add_argument('--size', type=int, nargs=2, default=(1024, 768))
    args = parser.parse_args()
    check(args.output.resolve(), tuple(args.size))
