"""核对本地KCD试驾的真实流送、原世界保持与往返释放；非人工或实时Gate。"""

import argparse
import faulthandler
import json
import os
import sys
import time
from dataclasses import asdict
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'src'))

from local_kcd_drive import LocalVegetation
from panda3d.core import Filename, GraphicsOutput, Texture

from application import CoastalDrive
from session import Phase
from vehicle_designs import vehicle_design
from vehicle_workspace import WorkspaceVehicle


def check(output, career_only=False, components=False, environment=None, lighting_diagnostics=False,
          material_diagnostics=False, onscreen=False, size=(1440, 810)):
    output.mkdir(parents=True, exist_ok=False)
    os.environ['LOCALAPPDATA'] = str(output / 'user')
    faulthandler.dump_traceback_later(120, repeat=True)
    profile = LocalVegetation(output / 'assets', environment)
    profile.install()
    app = None
    records = []
    try:
        app = CoastalDrive(smoke=True, onscreen=onscreen, output=output, render_size=size, threading_model='',
                           workspace_vehicle=WorkspaceVehicle('porsche-930', vehicle_design('porsche-930').config))
        app.taskMgr.remove('finish-smoke')
        app.taskMgr.remove('drive-update')
        readback = None
        if onscreen:
            # 窗口前缓冲在被桌面合成器遮挡时可能回读全黑；从同一窗口最终颜色缓冲复制。
            readback = Texture('local-onscreen-final-color')
            app.win.addRenderTexture(readback, GraphicsOutput.RTMCopyRam, GraphicsOutput.RTPColor)

        def capture(name):
            app.refresh_panel()
            app.apply_scene(app.session.current, 0)
            app.hud.resize(app.getAspectRatio())
            app.hud.update(app.session.current, app.session.race.snapshot, app.session.highway.snapshot,
                           track=app.session.simulation.track, countdown='', notice='',
                           driving_mode=app.session.driving_mode)
            frozen = asdict(app.session.current)
            samples = []
            for frame in range(38):
                began = time.perf_counter()
                app.taskMgr.step()
                if frame >= 8:
                    samples.append((time.perf_counter() - began) * 1000)
            app.graphicsEngine.syncFrame()
            assert asdict(app.session.current) == frozen
            assert not app.scene.expressway_kit['local-kcd-grass'].getShader().getErrorFlag()
            assert not app.scene.expressway_kit['route-terrain-shader'].getErrorFlag()
            assert not app.scene.expressway_kit['road-asphalt-shader'].getErrorFlag()
            assert all(not node.getShader().getErrorFlag() for node in app.scene.expressway_kit['local-rocks'].values())
            image_path = output / (name + '.png')
            (readback if onscreen else app.win.getScreenshot()).write(Filename.fromOsSpecific(str(image_path)))
            low, high = Image.open(image_path).convert('L').getextrema()
            assert high - low > 32, ('无有效画面，不能作为可见渲染证据', image_path)
            records.append({'view': name, 'tick': app.session.current.tick,
                            'position': list(app.session.current.player.position),
                            'segments': sorted(app.scene.segment_nodes),
                            'grass_groups': app.scene.render.findAllMatches('**/local-kcd-grass-distance').getNumPaths(),
                            'grass_instances': sum(node.getChild(0).getInstanceCount() for node in
                                                   app.scene.render.findAllMatches('**/local-kcd-grass-distance')),
                            'static_frame_ms': samples})
            (output / 'captures.json').write_text(json.dumps(records, ensure_ascii=False, indent=2), encoding='utf-8')
            print('CAPTURED', name, records[-1]['position'], flush=True)

        def start(shape):
            app.start_highway(shape)
            while app.session.phase == Phase.COUNTDOWN:
                app.session.tick()
            assert app.session.phase == Phase.DRIVING

        new_steps, retired = 0, []
        if not career_only:
            start('straight')
            beginning = app.session.current.tick
            app.session.keyboard.press('w')
            initial_roots = dict(app.scene.segment_nodes)
            for target in (20, 240, 440):
                while app.session.current.player.position[1] < target:
                    app.session.tick()
                    assert app.session.phase == Phase.DRIVING
                    if (app.session.current.tick - beginning) % 120 == 0:
                        app.scene.sync_segments()
                app.scene.sync_segments()
                capture('straight-' + str(target))
            app.session.keyboard.clear()
            new_steps = app.session.current.tick - beginning
            retired = [root for index, root in initial_roots.items() if index not in app.scene.segment_nodes]
            assert retired and all(root.isEmpty() for root in retired)
            root = app.scene.render
            app.back_to_menu()
            assert root.isEmpty() and app.scene is None
            start('hills')
            for _ in range(240):
                app.session.tick()
            capture('hills-start')
        app.back_to_menu()
        app.open_career()
        app.career_progress.records = {name: {'stars': 3, 'seconds': 20.} for name in ('first-drive', 'parking')}
        app.career_action('start', 'coast-sprint')
        while app.session.phase == Phase.COUNTDOWN:
            app.session.tick()
        for _ in range(240):
            app.session.tick()
        capture('coast-club-start')
        app.back_to_menu()
        app.open_career()
        # 只给本轮隔离的美术核对解锁赛事，未写入玩家进度或冒充实际获奖。
        app.career_progress.records = {name: {'stars': 3, 'seconds': 20.} for name in ('first-drive', 'parking')}
        app.career_action('start', 'ridge-run')
        while app.session.phase == Phase.COUNTDOWN:
            app.session.tick()
        for _ in range(240):
            app.session.tick()
        capture('ridge-club-start')
        camera = app.camera.getTransform()
        app.aspect2d.hide()
        app.camera.setPos(-9, 19, 18.0)
        app.camera.lookAt(-27, 32, 16.1)
        app.scene.sky.setPos(app.camera.getPos())
        app.scene.update_lighting(app.camera.getPos())
        # 仅换镜头；保持相同权威快照。
        for _ in range(12):
            app.taskMgr.step()
        app.win.getScreenshot().write(Filename.fromOsSpecific(str(output / 'ridge-tree-roots.png')))
        app.camera.setTransform(camera)
        app.aspect2d.show()
        app.scene.sky.setPos(app.camera.getPos())
        app.scene.update_lighting(app.camera.getPos())
        if lighting_diagnostics:
            from kcd_lighting_diagnostics import inspect_lighting

            inspect_lighting(app, output)
        if material_diagnostics:
            from kcd_lighting_diagnostics import inspect_materials

            inspect_materials(app, output)
        if components:
            app.taskMgr.remove('render-frame-pacing')
            grasses = tuple(app.scene.render.findAllMatches('**/local-kcd-grass-distance'))
            trees = tuple(node for node in app.scene.render.findAllMatches('**/+LODNode')
                          if node.getName().startswith('kcd-oak-'))
            timings = {}

            def measure(name):
                values = []
                for frame in range(70):
                    began = time.perf_counter()
                    app.taskMgr.step()
                    app.graphicsEngine.syncFrame()
                    if frame >= 10:
                        values.append((time.perf_counter() - began) * 1000)
                timings[name] = values

            measure('all')
            for node in grasses:
                node.hide()
            measure('without-grass')
            for node in trees:
                node.hide()
            measure('without-grass-and-trees')
            for node in (*grasses, *trees):
                node.show()
            measure('restored-all')
            (output / 'component-times.json').write_text(json.dumps(timings, indent=2), encoding='utf-8')
        root = app.scene.render
        app.back_to_menu()
        assert root.isEmpty() and app.scene is None
        scope = ('两赛道各240步起步与固定快照渲染' if career_only else '真实起步和直路440米流送')
        report = {'scope': scope + '；静态帧耗不代表实时或人工驾驶通过',
                  'onscreen': onscreen, 'size': list(size), 'window_type': type(app.win).__name__,
                  'new_straight_driving_steps': new_steps, 'hills_steps': 0 if career_only else 240,
                  'ridge_steps': 240, 'coast_steps': 240,
                  'retired_roots_removed': len(retired), 'menu_scene_released': root.isEmpty(), 'views': records}
        (output / 'summary.json').write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    finally:
        if app is not None:
            app.close_game()
        profile.restore()
        faulthandler.cancel_dump_traceback_later()


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--career-only', action='store_true')
    parser.add_argument('--components', action='store_true')
    parser.add_argument('--environment', type=Path)
    parser.add_argument('--lighting-diagnostics', action='store_true')
    parser.add_argument('--material-diagnostics', action='store_true')
    parser.add_argument('--onscreen', action='store_true')
    parser.add_argument('--size', type=int, nargs=2, default=(1440, 810))
    args = parser.parse_args()
    check(args.output.resolve(), args.career_only, args.components,
          None if args.environment is None else args.environment.resolve(), args.lighting_diagnostics,
          args.material_diagnostics, args.onscreen, tuple(args.size))
