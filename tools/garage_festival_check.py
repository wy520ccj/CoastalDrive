"""隔离存档检查车库实际界面和换车改装；界面解锁使用明确合成夹具。"""

import argparse
import gzip
import json
import os
import shutil
import sys
from dataclasses import asdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'src'))

from panda3d.core import Filename

from application import CoastalDrive
from career_garage import saved_paint, saved_vehicle
from career_run import CareerResult
from session import Phase
from vehicle_workspace import WorkspaceVehicle


def check(output, size, reuse_road=None):
    output.mkdir(parents=True, exist_ok=False)
    os.environ['LOCALAPPDATA'] = str(output/'isolated-user')
    app = CoastalDrive(smoke=True, output=output, render_size=size)
    app.taskMgr.remove('finish-smoke')
    app.taskMgr.remove('drive-update')
    captures, road_cases = [], []

    def capture(name):
        before = asdict(app.session.current)
        app.main_menu.resize(app.getAspectRatio())
        if app.session.phase in (Phase.COUNTDOWN, Phase.DRIVING):
            app.hud.resize(app.getAspectRatio())
            app.apply_scene(app.session.current, 0.)
            app.hud.update(app.session.current, app.session.race.snapshot, app.session.highway.snapshot,
                track=app.session.simulation.track, countdown='', notice='', driving_mode=app.session.driving_mode)
        for _ in range(6):
            app.taskMgr.step()
        app.graphicsEngine.syncFrame()
        app.win.getScreenshot().write(Filename.fromOsSpecific(str(output/(name+'.png'))))
        assert before == asdict(app.session.current)
        captures.append(name)

    try:
        app.main_menu.actions[3]()
        capture('01-garage')
        original = app.workspace_vehicle
        app.career_action('garage-car', 'coastal-hatch')
        assert app.workspace_vehicle == original
        capture('02-hatch-preview')
        app.career_action('garage-orbit', 110)
        capture('03-hatch-rear')
        app.career_action('garage-orbit', -110)
        app.career_action('garage-select')
        assert app.workspace_vehicle.design_id == 'coastal-hatch'
        assert WorkspaceVehicle.load(app.workspace_path) == app.workspace_vehicle
        hatch_skin = app.skin_index
        capture('04-hatch-selected')
        app.career_action('garage-tab', 'paint')
        app.career_action('garage-paint', 1)
        assert app.skin_index == hatch_skin
        capture('05-paint-preview')
        app.career_action('garage-back')
        app.career_action('garage')
        assert app.career_preview_skin == hatch_skin
        app.career_action('garage-tab', 'paint')
        app.career_action('garage-paint', 1)
        app.career_action('garage-paint-save')
        assert app.skin_index == 1
        assert saved_paint(app.career_garage_folder, app.workspace_vehicle.design_id) == 1
        capture('06-paint-saved')
        # 只用于看清锁定/解锁与改装界面；不记作新的实际驾驶成绩。
        for event in ('first-drive', 'parking', 'slalom'):
            app.career_progress.record(CareerResult(event, 8., elapsed=25., finished=True, succeeded=True, stars=3))
        app.career_action('garage-tab', 'upgrade')
        capture('07-upgrades')
        app.career_action('part', 'sport-front')
        tuned = app.workspace_vehicle
        assert tuned.config.lateral_stiffness == 70000.
        capture('08-installed')
        app.career_action('garage-tab', 'cars')
        for design_id, name in (('coastal-roadster', '09-roadster'),
                                ('gr86-2022-premium-6mt', '10-gr86'), ('coastal-gt', '11-gt')):
            app.career_action('garage-car', design_id)
            capture(name)
            app.career_action('garage-select')
            assert app.workspace_vehicle.design_id == design_id
            assert app.session.base_vehicle_config == app.workspace_vehicle.config
        app.career_action('garage-car', 'coastal-hatch')
        app.career_action('garage-select')
        assert app.workspace_vehicle == tuned
        assert app.skin_index == 1
        assert saved_vehicle(app.workspace_vehicle, original.design_id, app.career_garage_folder) == original
        assert WorkspaceVehicle.load(app.workspace_path) == tuned
        capture('12-restored-hatch')
        app.career_action('brief', 'parking')
        app.career_action('garage')
        app.career_action('garage-back')
        assert app.career_panel.page == 'brief' and app.career_panel.event_id == 'parking'
        capture('13-return-to-event')
        if reuse_road is not None:
            source = json.loads((reuse_road/'summary.json').read_text(encoding='utf-8'))
            assert source['passed'] and tuple(source['size']) == size
            road_cases = source['road_cases']
            for path in (*reuse_road.glob('14-road-*.png'), *reuse_road.glob('*-road.json.gz')):
                shutil.copy2(path, output/path.name)
            captures.extend('14-road-'+case['design_id'] for case in road_cases)
        for design_id in (() if reuse_road is not None else ('coastal-hatch', 'coastal-roadster', 'coastal-gt')):
            app.career_action('garage')
            app.career_action('garage-tab', 'cars')
            app.career_action('garage-car', design_id)
            app.career_action('garage-select')
            app.career_action('start', 'first-drive')
            while app.session.phase == Phase.COUNTDOWN:
                app.session.tick()
            initial = app.session.highway_progress()
            rows = []
            app.session.keyboard.press('w')
            for _ in range(240):
                app.session.tick()
                rows.append(asdict(app.session.current.player))
            app.session.keyboard.clear()
            assert app.session.highway_progress() > initial+1
            app.refresh_panel()
            capture('14-road-'+design_id)
            with gzip.open(output/(design_id+'-road.json.gz'), 'wt', encoding='utf-8') as stream:
                json.dump({'design_id': design_id, 'config': asdict(app.session.vehicle_config), 'rows': rows}, stream)
            road_cases.append({'design_id': design_id, 'new_driving_steps': 240,
                               'distance': app.session.highway_progress()-initial})
        summary = {'passed': True, 'captures': captures, 'size': size,
            'new_driving_steps': 720 if reuse_road is None else 0,
            'reused_driving_steps': 0 if reuse_road is None else 720,
            'road_source': str(reuse_road) if reuse_road is not None else None,
            'road_cases': road_cases,
            'scope': '真实渲染/预览取消/逐车改装和颜色保存/返回赛事；界面星级为夹具；'+
                ('道路复用原三车各240拍，不是新驾驶' if reuse_road is not None else '三车道路各240新拍仅验起步与显示')}
        (output/'summary.json').write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding='utf-8')
        print(json.dumps(summary, ensure_ascii=False))
    finally:
        app.close_game()


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--size', type=int, nargs=2, default=(1280, 720))
    parser.add_argument('--reuse-road', type=Path)
    args = parser.parse_args()
    check(args.output.resolve(), tuple(args.size), args.reuse_road)
