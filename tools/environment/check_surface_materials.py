"""实际起步后采集材质、斜视与近景，固定快照并核对GPU编译和权威世界。"""

import argparse
import json
import os
import sys
from dataclasses import asdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT/'src'))

from panda3d.core import Filename, SceneGraphAnalyzer

from application import CoastalDrive
from session import Phase
from vehicle_designs import vehicle_design
from vehicle_workspace import WorkspaceVehicle


def check(output, size):
    output.mkdir(parents=True, exist_ok=False)
    os.environ['LOCALAPPDATA'] = str(output/'user')
    app = CoastalDrive(smoke=True, output=output, render_size=size,
        workspace_vehicle=WorkspaceVehicle('porsche-930', vehicle_design('porsche-930').config))
    app.taskMgr.remove('finish-smoke')
    app.taskMgr.remove('drive-update')
    rows = []

    def capture(name):
        state = asdict(app.session.current)
        for _ in range(8):
            app.taskMgr.step()
        app.graphicsEngine.syncFrame()
        assert asdict(app.session.current) == state
        assert not app.scene.expressway_kit['road-asphalt-shader'].getErrorFlag()
        if 'foliage-shader' in app.scene.expressway_kit:
            assert not app.scene.expressway_kit['foliage-shader'].getErrorFlag()
        environment = app.scene.expressway_kit['daylight-environment']
        for part in (app.scene.render, app.scene.player, *app.scene.wheels):
            assert part.getShaderInput('filtered_env_map').getTexture() == environment.filtered_env_map
        app.win.getScreenshot().write(Filename.fromOsSpecific(str(output/(name+'.png'))))
        rows.append({'file': name+'.png', 'camera': list(app.camera.getPos()),
                     'snapshot_tick': app.session.current.tick})

    try:
        app.skin_index = 4
        app.open_career()
        app.career_action('start', 'first-drive')
        while app.session.phase == Phase.COUNTDOWN:
            app.session.tick()
        first = app.session.current.tick
        app.session.keyboard.press('w')
        for _ in range(240):
            app.session.tick()
        app.session.keyboard.clear()
        assert app.session.phase == Phase.DRIVING
        steps = app.session.current.tick-first
        app.refresh_panel()
        app.apply_scene(app.session.current, 0.)
        app.hud.resize(app.getAspectRatio())
        app.hud.update(app.session.current, app.session.race.snapshot, app.session.highway.snapshot,
            track=app.session.simulation.track, countdown='', notice='', driving_mode=app.session.driving_mode)
        capture('01-driving')
        app.aspect2d.hide()
        for name, position, target in (
            ('02-road-close', (-2., 12., .8), (-2., 25., .1)),
            ('03-verge', (-6.5, 45., 2.0), (-17., 57., -.2)),
            ('04-segment-seam', (0., 190., 2.5), (0., 215., .1)),
        ):
            app.camera.setPos(*position)
            app.camera.lookAt(*target)
            app.scene.sky.setPos(app.camera.getPos())
            app.scene.update_lighting(app.camera.getPos())
            capture(name)
        graph = SceneGraphAnalyzer()
        graph.addNode(app.scene.render.node())
        report = {'passed': True, 'size': size, 'captures': rows, 'new_driving_steps': steps,
            'snapshot': asdict(app.session.current), 'geoms': graph.getNumGeoms(), 'triangles': graph.getNumTris(),
            'scope': '240实际起步驾驶拍；其后仅固定快照下移动显示相机。非完整赛事/正式性能或人工验收。'}
        (output/'summary.json').write_text(json.dumps(report, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
        print('PASSED', output, 'new driving steps:', steps)
    finally:
        app.close_game()


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--size', nargs=2, type=int, default=(1280, 720))
    args = parser.parse_args()
    check(args.output.resolve(), tuple(args.size))
