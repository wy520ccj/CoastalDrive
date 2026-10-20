"""配方原页与候选的实际截图；仅预览，不安装或生成新道路成绩。"""

import argparse
import json
import math
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'src'))

from panda3d.core import Filename
from PIL import Image, ImageChops

from application import CoastalDrive
from race import GameMode


def check(output, size):
    output.mkdir(parents=True)
    os.environ['LOCALAPPDATA'] = str(output/'user-data')
    app = CoastalDrive(smoke=True, output=output, render_size=tuple(size), independent_clock=True)
    app.taskMgr.remove('finish-smoke')
    app.taskMgr.remove('drive-update')
    app.back_to_menu()
    before, car = app.session.current, app.workspace_vehicle
    images = []
    try:
        for name, choose, open_panel in (
                ('tires', lambda: app.choose_slalom_lesson(GameMode.FAST_SLALOM), app.open_tire_tuning),
                ('brakes', lambda: app.choose_braking_lesson(GameMode.SHORT_BRAKING), app.open_brake_tuning)):
            choose()
            open_panel()
            title_image = None
            for suffix, action in (('current', lambda: None), ('preview', lambda: app.tire_tuning.activate(3))):
                action()
                app.main_menu.resize(app.getAspectRatio())
                for _ in range(6):
                    app.taskMgr.step()
                app.graphicsEngine.renderFrame()
                app.graphicsEngine.renderFrame()
                app.graphicsEngine.syncFrame()
                image_name = name+'-'+suffix
                assert app.win.getScreenshot().write(Filename.fromOsSpecific(str(output/(image_name+'.png'))))
                lower, upper = app.tire_tuning.title.getTightBounds(app.render2d)
                box = (math.floor((lower.x+1)*size[0]/2)-2, math.floor((1-upper.z)*size[1]/2)-2,
                       math.ceil((upper.x+1)*size[0]/2)+2, math.ceil((1-lower.z)*size[1]/2)+2)
                with Image.open(output/(image_name+'.png')) as screenshot:
                    title = screenshot.crop(box).convert('RGB')
                if title_image is not None:
                    assert ImageChops.difference(title_image, title).getbbox() is None
                title_image = title
                images.append(image_name)
            app.key_down('escape')
            app.key_up('escape')
            assert app.tire_tuning.root.isHidden() and not app.panel.isHidden()
            assert app.workspace_vehicle == car and app.session.current == before
        (output/'summary.json').write_text(json.dumps({'passed': True, 'images': images, 'size': size,
            'scope': '实际原页/候选预览，不安装或新跑道路', 'snapshot_and_car_unchanged': True,
            'titles_unchanged_after_preview': True},
            ensure_ascii=False, indent=2), encoding='utf-8')
        return {'passed': True, 'images': len(images)}
    finally:
        app.close_game()


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--size', type=int, nargs=2, default=(1280, 720))
    args = parser.parse_args()
    print(json.dumps(check(args.output.resolve(), args.size), ensure_ascii=False))
