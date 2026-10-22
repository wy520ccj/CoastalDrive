"""隔离比较车库反射方向与布光；不改运行资产、配置或玩家存档。"""

import argparse
import json
import os
import sys
from dataclasses import asdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'src'))

from panda3d.core import Filename
from simplepbr.envmap import EnvMap

from application import CoastalDrive
from ui.garage_paint import garage_paint_shader
from vehicle_visual import set_vehicle_reflection


def capture(output, environment, design):
    output.mkdir(parents=True, exist_ok=False)
    os.environ['LOCALAPPDATA'] = str(output/'user')
    app = CoastalDrive(smoke=True, output=output)
    app.taskMgr.remove('finish-smoke')
    app.taskMgr.remove('drive-update')
    names = []
    try:
        app.open_career_collection()
        app.career_action('garage-car', design)
        view = app.workshop_vehicle
        before = asdict(app.session.current)

        def shot(name):
            for _ in range(8):
                app.taskMgr.step()
            app.graphicsEngine.syncFrame()
            app.win.getScreenshot().write(Filename.fromOsSpecific(str(output/(name+'.png'))))
            assert asdict(app.session.current) == before
            names.append(name+'.png')

        shot('01-before')
        corrected = EnvMap.from_file_path(Filename.fromOsSpecific(str(environment)))
        view.pipeline.env_map = corrected
        nodes = (view.car_root.getChild(0), *view.wheels)
        for node in nodes:
            set_vehicle_reflection(node, corrected)
        shot('02-corrected')
        for node in view.car_root.findAllMatches('**/paint'):
            node.setShader(garage_paint_shader(view.pipeline.use_330), 2)
        shot('02b-clearcoat')
        for node in nodes:
            node.setLightOff(2)
        shot('03-hdri-only')
        for exposure in (-1., -2.):
            view.pipeline.exposure = exposure
            shot(f'04-hdri-exposure-{exposure}')
        report = {'passed': True, 'environment': str(environment), 'captures': names,
                  'new_driving_steps': 0, 'scope': '同窗口/相机/原真实车漆，只比较环境反射与布光；不是人工审美验收'}
        (output/'summary.json').write_text(json.dumps(report, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
        print(json.dumps(report, ensure_ascii=False))
    finally:
        app.close_game()


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--environment', type=Path, required=True)
    parser.add_argument('--car', default='game-tuned')
    args = parser.parse_args()
    capture(args.output.resolve(), args.environment.resolve(), args.car)
