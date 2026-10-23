"""按设计规格采集实际车库三页，验证新资源、正常操作与显示生命周期。"""

import argparse
import json
import os
import sys
from dataclasses import asdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'src'))

from panda3d.core import Filename

from application import CoastalDrive
from career_run import CareerResult
from session import Phase
from vehicle_workspace import WorkspaceVehicle


def check(output, size, design_id='coastal-gt'):
    output.mkdir(parents=True, exist_ok=False)
    os.environ['LOCALAPPDATA'] = str(output/'user')
    app = CoastalDrive(smoke=True, output=output, render_size=size)
    app.taskMgr.remove('finish-smoke')
    app.taskMgr.remove('drive-update')
    captures, bounds = [], []

    def capture(name):
        before = asdict(app.session.current)
        for _ in range(8):
            app.taskMgr.step()
        app.graphicsEngine.syncFrame()
        app.win.getScreenshot().write(Filename.fromOsSpecific(str(output/(name+'.png'))))
        assert before == asdict(app.session.current)
        captures.append(name)
        if app.career_panel.page != 'garage':
            return
        panel, view = app.career_panel, app.workshop_vehicle
        left, right, bottom, top = view.frame['frameSize']
        for button in panel.buttons:
            x, z = button.getX(), button.getZ()
            l, r, b, t = button['frameSize']
            assert min(right, x+r) <= max(left, x+l) or min(top, z+t) <= max(bottom, z+b)
        from ui.garage_framing import project_vertices

        points = project_vertices(view.framing_vertices, view.scene, view.camera)
        assert points is not None
        assert (abs(points[:, 0]) <= .91).all() and (abs(points[:, 1]) <= .87).all()
        bounds.append({'page': name, 'vehicle_frame': list(view.frame['frameSize']),
            'projected_x': [min(p[0] for p in points), max(p[0] for p in points)],
            'projected_y': [min(p[1] for p in points), max(p[1] for p in points)]})

    try:
        app.open_career_collection()
        capture('01-collection-locked')
        original, snapshot = app.workspace_vehicle, app.session.current
        # 锁定分支固定用9星车型，低星/初始车型也能复用完整采集流程。
        app.career_action('garage-car', 'coastal-gt')
        app.career_action('garage-select')
        assert app.workspace_vehicle == original and app.session.current == snapshot
        for event in ('first-drive', 'parking', 'slalom'):
            app.career_progress.record(CareerResult(event, 8., elapsed=25., finished=True, succeeded=True, stars=3))
        app.career_action('garage-car', design_id)
        app.career_action('garage-select')
        assert app.workspace_vehicle.design_id == design_id
        selected = app.workspace_vehicle
        capture('02-collection-concept')
        app.career_action('garage-tab', 'upgrade')
        capture('03-upgrade-tires')
        app.career_action('part', 'sport-front')
        assert app.workspace_vehicle.config.lateral_stiffness == 70000.
        capture('04-upgrade-installed')
        app.career_action('garage-topic', 'brakes')
        capture('05-upgrade-brakes')
        app.career_action('garage-tab', 'paint')
        old_skin = app.skin_index
        app.career_action('garage-paint', (old_skin+1) % 5)
        assert old_skin != app.career_preview_skin
        capture('06-paint-preview')
        app.career_action('garage-tab', 'paint')
        assert app.career_preview_skin == old_skin
        app.career_action('garage-paint', 4)
        app.career_panel.select(len(app.career_panel.buttons)-1)
        app.career_panel.key('arrow_up')
        assert app.career_panel.selected == app.career_panel.primary
        app.career_panel.key('enter')
        assert app.skin_index == 4
        capture('07-paint-saved')
        windows = app.graphicsEngine.getNumWindows()
        for _ in range(2):
            for tab in ('cars', 'upgrade', 'paint'):
                app.career_action('garage-tab', tab)
        assert app.graphicsEngine.getNumWindows() == windows
        for index, angle in enumerate((50, -100, 50)):
            app.career_action('garage-orbit', angle)
            capture('08-orbit-'+str(index))
        app.career_action('garage-tab', 'upgrade')
        app.career_action('restore')
        assert app.workspace_vehicle == selected
        assert WorkspaceVehicle.load(app.workspace_path) == selected
        app.career_action('brief', 'parking')
        app.career_action('garage')
        app.career_action('garage-back')
        assert app.career_panel.page == 'brief' and app.career_panel.event_id == 'parking'
        capture('09-return-to-event')
        app.career_action('start', 'first-drive')
        while app.session.phase == Phase.COUNTDOWN:
            app.session.tick()
        app.session.keyboard.press('w')
        for _ in range(240):
            app.session.tick()
        app.session.keyboard.clear()
        app.refresh_panel()
        assert app.session.phase == Phase.DRIVING and app.main_menu.root.isHidden()
        app.apply_scene(app.session.current, 0.)
        app.hud.resize(app.getAspectRatio())
        app.hud.update(app.session.current, app.session.race.snapshot, app.session.highway.snapshot,
            track=app.session.simulation.track, countdown='', notice='', driving_mode=app.session.driving_mode)
        capture('10-concept-road')
        summary = {'passed': True, 'size': size, 'captures': captures, 'layout': bounds,
            'new_driving_steps': 240, 'display_worlds': 0,
            'scope': '实际界面/有来源模型/选车锁定/购件恢复/颜色预览取消保存/正常键盘返回/显示资源不累积；9星为界面夹具；240新拍仅验新车模道路显示，不替代完整驾驶或人工审美'}
        (output/'summary.json').write_text(json.dumps(summary, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
        print(json.dumps(summary, ensure_ascii=False))
    finally:
        app.close_game()


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--size', nargs=2, type=int, default=(1280, 720))
    parser.add_argument('--car', default='coastal-gt')
    args = parser.parse_args()
    check(args.output.resolve(), tuple(args.size), args.car)
