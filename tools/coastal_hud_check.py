"""滨海HUD两画幅真实渲染；赛况为排版夹具，不冒充正常驾驶。"""

import argparse
import json
import os
import sys
from dataclasses import asdict, replace
from pathlib import Path

from panda3d.core import Filename

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'src'))

from application import CoastalDrive
from driving_modes import DrivingMode
from race import GameMode, RaceSnapshot


def check(output, size):
    output.mkdir(parents=True, exist_ok=False)
    os.environ['LOCALAPPDATA'] = str(output/'user')
    app = CoastalDrive(smoke=True, output=output, render_size=size)
    app.taskMgr.remove('finish-smoke')
    app.taskMgr.remove('drive-update')
    reports = []
    try:
        app.start_game(mode=GameMode.TIME_TRIAL, track='coastal')
        app.apply_scene(app.session.current, 0.)
        app.hud.resize(app.getAspectRatio())
        app.layout_driving_buttons()
        app.hud.root.show()
        app.panel.hide()
        app.main_menu.root.hide()
        app.workshop_vehicle.hide()
        original = asdict(app.session.current)
        race = RaceSnapshot(mode=GameMode.TIME_TRIAL, elapsed=42.73, checkpoints=2,
            next_checkpoint=3, splits=(21., 40.), reference_splits=(20., 41., 50., 60., 70.),
            reference_lap=70., best_lap=50.)
        cases = (
            ('free', replace(race, mode=GameMode.FREE_DRIVE), DrivingMode.GAME, '', None),
            ('start', RaceSnapshot(mode=GameMode.TIME_TRIAL), DrivingMode.GAME, '', None),
            ('split', race, DrivingMode.GAME, '', None),
            ('invalid', replace(race, invalidated=True, invalid_reason='车辆复位'), DrivingMode.GAME, '', None),
            ('simulation-radio', race, DrivingMode.SIMULATION, '', 1),
            ('warning', replace(race, score_notice='成绩暂未保存，请检查存储空间或目录权限。',
                ghost_notice='最佳圈幽灵未读取，本次仍可正常驾驶。'), DrivingMode.GAME, '工坊道路验证：按顺序通过检查点，完成有效圈。', None),
        )
        for name, state, driving_mode, notice, station in cases:
            app.hud.select_radio(station)
            app.hud.update(app.session.current, state, app.session.highway.snapshot,
                           track='coastal', countdown='', notice=notice, driving_mode=driving_mode)
            app.ghost_button.show() if state.mode == GameMode.TIME_TRIAL else app.ghost_button.hide()
            app.taskMgr.step()
            for _ in range(6):
                app.graphicsEngine.renderFrame()
            path = output/(name+'.png')
            assert app.win.saveScreenshot(Filename.fromOsSpecific(str(path)))
            view = app.hud.coastal
            labels = [view.title]
            if state.mode == GameMode.TIME_TRIAL:
                labels += [view.timer, view.checkpoints, view.sector, view.cumulative, view.goal]
            bounds = []
            for label in labels:
                lower, upper = label.getTightBounds(view.status)
                fits = lower.x >= 0 and upper.x <= 360 and lower.z >= view.status['frameSize'][2] and upper.z <= 0
                bounds.append({'text':label.getText(), 'fits':fits,'lower':list(lower),'upper':list(upper)})
            assert asdict(app.session.current) == original
            reports.append({'case':name, 'image':path.name, 'bounds':bounds,
                            'passed':all(row['fits'] for row in bounds)})
        report = {'passed':all(row['passed'] for row in reports), 'size':size, 'cases':reports,
                  'scope':'真实Scene/UI渲染，赛况排版夹具，0新增道路拍；完整Snapshot保持，不作为正常驾驶或性能Gate。'}
        (output/'summary.json').write_text(json.dumps(report, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
        print(json.dumps({'passed':report['passed'],'cases':len(reports)}))
        return report['passed']
    finally:
        app.close_game()


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--size', type=int, nargs=2, default=(1280, 720))
    args = parser.parse_args()
    raise SystemExit(0 if check(args.output.resolve(), tuple(args.size)) else 1)
