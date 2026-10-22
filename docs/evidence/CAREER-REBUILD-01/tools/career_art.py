"""以项目真实场景制作赛事缩略图；仅移动拍摄相机，不移动或推进车辆。"""

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
from career import EVENTS
from race import GameMode


def capture(output, events):
    output.mkdir(parents=True, exist_ok=False)
    os.environ['LOCALAPPDATA'] = str(output/'isolated-user')
    app = CoastalDrive(smoke=True, output=output/'runtime', render_size=(1280, 720))
    app.taskMgr.remove('finish-smoke')
    app.taskMgr.remove('drive-update')
    rows = []
    try:
        for event in EVENTS:
            if events and event.id not in events:
                continue
            app.career_event_id = event.id
            app._enter_game(GameMode.CAREER, 'endless')
            for _ in range(360):
                app.session.tick()
            app.scene.apply(app.session.current)
            road = app.session.simulation.road
            progress = app.session.highway.snapshot.career.start_progress
            if event.kind in ('slalom', 'parking'):
                distance = event.gates[0][0] if event.gates else event.distance
                point = road.sample_lateral(progress+distance-22., 0.)
                target = road.sample_lateral(progress+distance+30., 0.)
                app.camera.setPos(point.x+6., point.y, point.z+6.)
                app.camera.lookAt(target.x, target.y, target.z)
            elif event.chapter > 0:
                distance = event.distance*.4
                point = road.sample_lateral(progress+distance, 6.)
                target = road.sample_lateral(progress+distance+60., 0.)
                app.camera.setPos(point.x, point.y, point.z+10.)
                app.camera.lookAt(target.x, target.y, target.z)
            else:
                car = app.session.current.player
                app.camera.setPos(car.position[0]+5.5, car.position[1]+8., car.position[2]+3.2)
                app.camera.lookAt(car.position[0], car.position[1]+1., car.position[2]+.4)
            app.aspect2d.hide()
            for _ in range(8):
                app.taskMgr.step()
            path = output/(event.id+'.png')
            app.win.getScreenshot().write(Filename.fromOsSpecific(str(path)))
            rows.append({'event': event.id, 'image': path.name, 'sha256': hashlib.sha256(path.read_bytes()).hexdigest(),
                         'initialisation_ticks': app.session.simulation.initialisation_ticks,
                         'driving_steps': 0, 'tick': app.session.current.tick})
        (output/'manifest.json').write_text(json.dumps({'source': 'CoastalDrive Panda3D renderer; existing project vehicles and roads',
            'process': 'Fixed camera capture with no UI; original PNGs copied without pixel edits', 'cases': rows},
            ensure_ascii=False, indent=2), encoding='utf-8')
        print(json.dumps(rows))
    finally:
        app.close_game()


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--events', nargs='*')
    args = parser.parse_args()
    capture(args.output.resolve(), args.events)
