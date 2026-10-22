"""只采集真实车库画面；解锁为隔离界面夹具，不运行道路物理。"""

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
from career import EVENTS
from career_run import CareerResult


def capture(output, size, design_id='coastal-gt', only=(), orbit=0., stars=9):
    output.mkdir(parents=True, exist_ok=False)
    os.environ['LOCALAPPDATA'] = str(output/'user')
    app = CoastalDrive(smoke=True, output=output, render_size=size)
    app.taskMgr.remove('finish-smoke')
    app.taskMgr.remove('drive-update')
    before = asdict(app.session.current)
    names = []
    try:
        app.open_career_collection()
        for event in EVENTS[:stars//3]:
            app.career_progress.record(CareerResult(event.id, 8., elapsed=25., finished=True, succeeded=True, stars=3))
        app.career_action('garage-car', design_id)
        app.career_action('garage-select')
        if orbit:
            app.career_action('garage-orbit', orbit)
        for tab, topic in (('cars', None), ('upgrade', 'tires'), ('upgrade', 'brakes'),
                           ('upgrade', 'power'), ('upgrade', 'suspension'), ('paint', None)):
            name = tab+('-'+topic if topic else '')+'.png'
            if only and name[:-4] not in only:
                continue
            app.career_action('garage-tab', tab)
            if topic is not None:
                app.career_action('garage-topic', topic)
            for _ in range(8):
                app.taskMgr.step()
            app.graphicsEngine.syncFrame()
            app.win.getScreenshot().write(Filename.fromOsSpecific(str(output/name)))
            names.append(name)
            assert asdict(app.session.current) == before
        report = {'passed': True, 'size': size, 'captures': names, 'orbit': orbit, 'stars': stars, 'new_driving_steps': 0,
                  'scope': '隔离星级夹具，仅采集静态页面；不重复道路驾驶，不替代原功能T1或人工观感'}
        (output/'summary.json').write_text(json.dumps(report, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
        print(json.dumps(report, ensure_ascii=False))
    finally:
        app.close_game()


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', required=True, type=Path)
    parser.add_argument('--size', nargs=2, type=int, default=(1280, 720))
    parser.add_argument('--car', default='coastal-gt')
    parser.add_argument('--only', nargs='+', default=())
    parser.add_argument('--orbit', type=float, default=0.)
    parser.add_argument('--stars', type=int, choices=range(0, 19, 3), default=9)
    args = parser.parse_args()
    capture(args.output.resolve(), tuple(args.size), args.car, args.only, args.orbit, args.stars)
