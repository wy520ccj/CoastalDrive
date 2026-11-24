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
from vehicle_designs import vehicle_design
from vehicle_workspace import WorkspaceVehicle


def _sync_camera_view(app, distance):
    """移动相机到远端弯道时同步流送路段与天空球位置，保证实拍与驾驶实机一致。"""
    app.scene.sync_segments(distance=distance)
    if getattr(app.scene, 'sky', None) is not None:
        app.scene.sky.setPos(app.camera.getPos())


def capture(output, events, design_id):
    output.mkdir(parents=True, exist_ok=True)
    os.environ['LOCALAPPDATA'] = str(output/'isolated-user')
    app = CoastalDrive(smoke=True, output=output/'runtime', render_size=(1280, 720),
        workspace_vehicle=WorkspaceVehicle(design_id, vehicle_design(design_id).config))
    app.taskMgr.remove('finish-smoke')
    app.taskMgr.remove('drive-update')
    rows = []
    try:
        for event in EVENTS:
            if events and event.id not in events:
                continue
            app.career_event_id = event.id
            app._enter_game(GameMode.CAREER, 'endless')
            for _ in range(180):
                app.session.tick()
            app.scene.apply(app.session.current)
            app.scene.sync_segments()
            road = app.session.simulation.road
            progress = app.session.highway.snapshot.career.start_progress
            if event.kind in ('slalom', 'parking'):
                distance = event.gates[0][0] if event.gates else event.distance
                cam_dist = progress + distance - 24.
                point = road.sample_lateral(cam_dist, 4.5)
                target = road.sample_lateral(progress + distance + 28., 0.)
                app.camera.setPos(point.x, point.y, point.z + 4.8)
                app.camera.lookAt(target.x, target.y, target.z + 0.6)
                _sync_camera_view(app, cam_dist)
            elif event.id == 'coastal-cup':
                cam_dist = progress + 520.
                point = road.sample_lateral(cam_dist, 3.8)
                target = road.sample_lateral(cam_dist + 68., 0.)
                app.camera.setPos(point.x, point.y, point.z + 5.2)
                app.camera.lookAt(target.x, target.y, target.z + 1.0)
                _sync_camera_view(app, cam_dist)
            # 其余赛事保留真实实机发车追车视角（含当前车型、天空、路牌与阴影），与实机画面 100% 一致。
            app.aspect2d.hide()
            before = app.session.current
            for _ in range(10):
                app.taskMgr.step()
            path = output/(event.id+'.png')
            app.win.getScreenshot().write(Filename.fromOsSpecific(str(path)))
            assert app.session.current == before
            rows.append({'event': event.id, 'image': path.name, 'sha256': hashlib.sha256(path.read_bytes()).hexdigest(),
                         'initialisation_ticks': app.session.simulation.initialisation_ticks,
                         'driving_steps': 0, 'tick': app.session.current.tick,
                         'design_id': design_id, 'visual': app.vehicle_model_id})

        if not events or 'chase-valley' in events:
            app._enter_game(GameMode.VALLEY_PACE, 'endless')
            for _ in range(180):
                app.session.tick()
            app.scene.apply(app.session.current)
            app.scene.sync_segments()
            app.aspect2d.hide()
            for _ in range(10):
                app.taskMgr.step()
            path = output/'chase-valley.png'
            app.win.getScreenshot().write(Filename.fromOsSpecific(str(path)))
            rows.append({'event': 'chase-valley', 'image': path.name, 'sha256': hashlib.sha256(path.read_bytes()).hexdigest(),
                         'initialisation_ticks': app.session.simulation.initialisation_ticks,
                         'driving_steps': 0, 'tick': app.session.current.tick,
                         'design_id': design_id, 'visual': app.vehicle_model_id})

        (output/'manifest.json').write_text(json.dumps({'source': 'CoastalDrive Panda3D renderer; current live scene vehicles sky and roads',
            'process': 'Live camera capture with synced road segments and sky dome; no UI and no pixel edits', 'cases': rows},
            ensure_ascii=False, indent=2), encoding='utf-8')
        print(json.dumps(rows))
    finally:
        app.close_game()


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--events', nargs='*')
    parser.add_argument('--car', default='game-tuned')
    args = parser.parse_args()
    capture(args.output.resolve(), args.events, args.car)
