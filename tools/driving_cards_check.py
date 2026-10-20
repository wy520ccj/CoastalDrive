"""驾驶菜单正常导航与实际截图；不运行新道路驾驶。"""

import argparse
import hashlib
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'src'))

from panda3d.core import Filename

from application import CoastalDrive
from race import GameMode


def check(output, size):
    output.mkdir(parents=True)
    os.environ['LOCALAPPDATA'] = str(output/'user-data')
    app = CoastalDrive(smoke=True, output=output, render_size=tuple(size), independent_clock=True)
    app.taskMgr.remove('finish-smoke')
    app.taskMgr.remove('drive-update')
    app.back_to_menu()
    before = app.session.current
    source = {name: hashlib.sha256((ROOT/name).read_bytes().replace(b'\r\n', b'\n')).hexdigest()
              for name in ('src/application.py', 'src/ui/driving_cards.py', 'tools/driving_cards_check.py')}
    images = []
    try:
        for name, action in (
                ('highway', app.choose_highway), ('routes', app.choose_sprint_routes),
                ('braking', app.choose_braking_lesson),
                ('short-braking', lambda: app.choose_braking_lesson(GameMode.SHORT_BRAKING)),
                ('slalom', app.choose_slalom_lesson),
                ('fast-slalom', lambda: app.choose_slalom_lesson(GameMode.FAST_SLALOM)),
                ('overtake', app.choose_overtake),
                ('hill-traffic', lambda: app.choose_overtake(GameMode.HILL_TRAFFIC))):
            action()
            for _ in range(4):
                app.taskMgr.step()
            app.graphicsEngine.syncFrame()
            assert app.win.getScreenshot().write(Filename.fromOsSpecific(str(output/(name+'.png'))))
            images.append(name)
            assert app.session.current == before
        app.handle_panel_key('escape')
        assert app.sprint_menu
        app.handle_panel_key('escape')
        assert app.highway_menu and not app.sprint_menu
        app.handle_panel_key('escape')
        assert not app.highway_menu and not app.main_menu.root.isHidden()
        assert not app.driving_cards.active and app.driving_cards.root.isHidden()
        assert app.session.current == before
        (output/'summary.json').write_text(json.dumps({'passed': True, 'images': images, 'size': size, 'source': source,
            'scope': '实际静态页面与正常返回，不新造道路驾驶/成绩', 'snapshot_unchanged': True},
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
