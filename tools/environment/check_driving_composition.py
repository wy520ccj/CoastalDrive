"""从静止真实驶入组合弯，以原跟车镜头验收草树地石；不模拟键盘或移动权威车辆。"""

import argparse
import json
import math
import os
import shutil
import subprocess
import sys
from dataclasses import asdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'src'))

from panda3d.core import Filename

from application import CoastalDrive
from driver_assist import steering_limit
from session import Phase
from simulation import Control
from vehicle_designs import vehicle_design
from vehicle_workspace import WorkspaceVehicle


class ViewDriver:
    """只用于美术取景的限速循线Controller，仍经过原Control/Simulation执行器。"""

    def __init__(self, session=None):
        self.simulation = None
        if session is not None:
            self.bind(session.simulation)

    def bind(self, simulation):
        self.simulation = simulation

    def sample(self, state, dt):
        road, car = self.simulation.road, state.player
        progress, _lateral = road.locate(car)
        look = 6 + abs(car.speed) * .6
        target = road.sample_lateral(progress + look, 0.)
        dx, dy = target.x - car.position[0], target.y - car.position[1]
        error = math.atan2(-dx, dy) - math.radians(car.heading)
        wheel = math.degrees(math.atan2(2 * self.simulation.config.wheelbase * math.sin(error),
                                        math.hypot(dx, dy)))
        steering = max(-1., min(1., -wheel / steering_limit(car.speed, self.simulation.config)))
        target_speed = 50 / 3.6
        for ahead in range(0, 101, 5):
            a, b = (road.sample_lateral(progress + ahead + offset, 0.) for offset in (-2., 2.))
            curvature = abs(math.radians((b.heading - a.heading + 180) % 360 - 180)) / 4
            target_speed = min(target_speed, math.sqrt(2.5 / max(curvature, .001) + 5 * ahead))
        delta = target_speed - car.speed
        return Control(steering=steering, throttle=max(0., min(1., .25 + delta * .22)),
                       brake=max(0., min(1., -delta * .25)) if delta < -.6 else 0.)


def check(output, baseline, size, diagnostics=False, end_distance=450, lighting_variants=False,
          foliage_variants=False, grass_variants=False, ground_variants=False, video=False,
          canopy_variants=False, rock_variants=False, transmission_variants=False, canopy_visibility=None,
          woodland_variants=False, inspect_at_120=None, hd2_rocks=False):
    if baseline:
        sys.path.insert(0, str(ROOT / 'logs/visual-upgrade-20261024/baseline'))
    from local_kcd_drive import LocalVegetation

    output.mkdir(parents=True, exist_ok=False)
    os.environ['LOCALAPPDATA'] = str(output / 'user')
    if baseline:
        profile = LocalVegetation(output / 'assets', ROOT / 'logs/local-kcd-original-environment')
    else:
        from local_kcd_drive import CANOPY_VISIBILITY

        profile = LocalVegetation(output / 'assets', ROOT / 'logs/local-kcd-original-environment',
                                  canopy_visibility=canopy_visibility if canopy_visibility is not None else CANOPY_VISIBILITY,
                                  hd2_rocks=hd2_rocks)
    profile.install()
    app, rows, views = None, [], []
    encoder, video_log, video_ticks = None, None, []
    try:
        app = CoastalDrive(smoke=True, output=output, render_size=size, threading_model='',
                           workspace_vehicle=WorkspaceVehicle('porsche-930', vehicle_design('porsche-930').config))
        app.taskMgr.remove('finish-smoke')
        app.taskMgr.remove('drive-update')
        if video:
            executable = shutil.which('ffmpeg')
            if executable is None:
                raise FileNotFoundError('连续取景需要本机ffmpeg')
            video_log = (output / 'video-encoder.log').open('w', encoding='utf-8')
            encoder = subprocess.Popen([
                executable, '-hide_banner', '-y', '-f', 'rawvideo', '-pixel_format', 'rgba',
                '-video_size', str(size[0]) + 'x' + str(size[1]), '-framerate', '15', '-i', 'pipe:0',
                '-vf', 'vflip,format=yuv420p', '-c:v', 'libx264', '-preset', 'fast', '-crf', '20',
                '-movflags', '+faststart', str(output / 'driving-view.mp4')],
                stdin=subprocess.PIPE, stdout=subprocess.DEVNULL, stderr=video_log,
                creationflags=subprocess.CREATE_NO_WINDOW)
        app.open_career()
        app.career_progress.records = {name: {'stars': 3, 'seconds': 20.} for name in ('first-drive', 'parking')}
        app.career_action('start', 'coast-sprint')
        while app.session.phase == Phase.COUNTDOWN:
            app.session.tick()
        app.session.set_controller(ViewDriver(app.session))
        initial = app.session.current.tick
        targets = iter(distance for distance in (40, 120, 190, 270, 360, 450) if distance <= end_distance)
        target = next(targets)
        frames = 0
        for step in range(120 * 90):
            app.session.tick()
            state = app.session.current
            progress = app.session.highway_progress()
            rows.append({'tick': state.tick, 'time': state.time, 'position': list(state.player.position),
                         'heading': state.player.heading, 'origin_y': state.origin_y,
                         'progress': progress, 'control': asdict(app.session.last_control),
                         'collisions': state.collisions})
            assert app.session.phase == Phase.DRIVING, ('行车取景提前结束', progress)
            if step % 8 == 0 or progress >= target:
                app.scene.sync_segments()
                app.apply_scene(state, 8 / 120)
                app.refresh_panel()
                app.hud.resize(app.getAspectRatio())
                app.hud.update(state, app.session.race.snapshot, app.session.highway.snapshot,
                               track='endless', countdown='', notice='', driving_mode=app.session.driving_mode)
                app.taskMgr.step()
                frames += 1
                if encoder is not None and step % 8 == 0:
                    app.graphicsEngine.syncFrame()
                    pixels = bytes(app.win.getScreenshot().getRamImageAs('RGBA'))
                    assert len(pixels) == size[0] * size[1] * 4
                    encoder.stdin.write(pixels)
                    video_ticks.append(state.tick)
            if progress >= target:
                frozen = asdict(state)
                for _ in range(12):
                    app.taskMgr.step()
                app.graphicsEngine.syncFrame()
                if canopy_visibility is not None and target == 120:
                    for label, strength in (('disabled', 0.), ('enabled', .7)):
                        app.scene.render.setShaderInput('local_canopy_occlusion', strength)
                        for _ in range(12):
                            app.taskMgr.step()
                        app.graphicsEngine.syncFrame()
                        app.win.getScreenshot().write(Filename.fromOsSpecific(str(output / ('canopy-' + label + '.png'))))
                for name in ('local-kcd-grass', 'local-kcd-grass-mid'):
                    assert not app.scene.expressway_kit[name].getShader().getErrorFlag(), name
                assert not app.scene.expressway_kit['route-terrain-shader'].getErrorFlag()
                image = app.win.getScreenshot()
                image.write(Filename.fromOsSpecific(str(output / (str(target) + 'm.png'))))
                if diagnostics and target == 190:
                    from kcd_lighting_diagnostics import inspect_materials

                    inspect_materials(app, output, driving_view=True)
                if lighting_variants and target == 120:
                    from kcd_lighting_diagnostics import inspect_sun_balance

                    inspect_sun_balance(app, output, profile.parameters)
                if foliage_variants and target == 120:
                    from kcd_lighting_diagnostics import inspect_foliage_distance

                    inspect_foliage_distance(app, output)
                if grass_variants and target == 120:
                    from kcd_lighting_diagnostics import inspect_grass_field

                    inspect_grass_field(app, output)
                if ground_variants and target in (120, 270):
                    from kcd_lighting_diagnostics import inspect_ground_match

                    inspect_ground_match(app, output / ('ground-' + str(target)))
                if woodland_variants and target == 120:
                    from kcd_lighting_diagnostics import inspect_woodland_cover

                    inspect_woodland_cover(app, output)
                if inspect_at_120 is not None and target == 120:
                    inspect_at_120(app, output)
                if canopy_variants and target == 120:
                    from kcd_lighting_diagnostics import inspect_canopy_shadows

                    inspect_canopy_shadows(app, output)
                if rock_variants and target == 120:
                    from kcd_lighting_diagnostics import inspect_rock_normals

                    inspect_rock_normals(app, output)
                if transmission_variants and target == 120:
                    from kcd_lighting_diagnostics import inspect_leaf_transmission

                    inspect_leaf_transmission(app, output)
                assert asdict(app.session.current) == frozen
                decorations = [node.getName() for root in app.scene.segment_nodes.values()
                               for node in root.findAllMatches('**/+LODNode')]
                counts = {kind: sum(name.startswith(prefix) for name in decorations)
                          for kind, prefix in (('oak', 'kcd-oak-'), ('young_oak', 'kcd-young-oak-'),
                                               ('sandstone', 'kcd-sandstone-'))}
                views.append({'target_m': target, 'progress_m': progress, 'camera': list(app.camera.getPos()),
                              'car': list(state.player.position), 'fov': app.camLens.getHfov(),
                              'streamed_decorations': counts})
                print('DRIVING VIEW', target, 'tick', state.tick, 'collisions', state.collisions, flush=True)
                target = next(targets, None)
                if target is None:
                    break
        assert target is None, ('未驶完取景段', target)
        if encoder is not None:
            encoder.stdin.close()
            assert encoder.wait(timeout=60) == 0, '视频编码失败，查看video-encoder.log'
        (output / 'actual-driving.json').write_text(json.dumps(rows), encoding='utf-8')
        summary = {'baseline': baseline, 'scope': '原120Hz物理与正常跟车镜头，非人工驾驶或实时性能Gate',
                   'new_driving_steps': app.session.current.tick - initial, 'display_frames': frames,
                   'collisions': app.session.current.collisions, 'views': views, 'size': list(size),
                   'render_buffers': [{'name': buffer.getName(), 'multisamples': buffer.getFbProperties().getMultisamples()}
                                      for buffer in app.pipeline._filtermgr.buffers]}
        if video:
            summary['video'] = {'file': 'driving-view.mp4', 'frames': len(video_ticks), 'fps': 15,
                                'first_tick': video_ticks[0], 'last_tick': video_ticks[-1], 'tick_stride': 8,
                                'scope': '正常随车实际渲染，按120Hz物理每8步采集；编码期间墙钟不代表实时性能'}
        (output / 'summary.json').write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding='utf-8')
    finally:
        if encoder is not None and encoder.poll() is None:
            encoder.terminate()
            encoder.wait(timeout=10)
        if video_log is not None:
            video_log.close()
        if app is not None:
            app.close_game()
        profile.restore()


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--baseline', action='store_true')
    parser.add_argument('--material-diagnostics', action='store_true')
    parser.add_argument('--size', type=int, nargs=2, default=(1440, 810))
    parser.add_argument('--end-distance', type=int, choices=(40, 120, 190, 270, 360, 450), default=450)
    parser.add_argument('--lighting-variants', action='store_true')
    parser.add_argument('--foliage-variants', action='store_true')
    parser.add_argument('--grass-variants', action='store_true')
    parser.add_argument('--ground-variants', action='store_true')
    parser.add_argument('--video', action='store_true')
    parser.add_argument('--canopy-variants', action='store_true')
    parser.add_argument('--rock-variants', action='store_true')
    parser.add_argument('--transmission-variants', action='store_true')
    parser.add_argument('--canopy-visibility', type=Path)
    parser.add_argument('--woodland-variants', action='store_true')
    args = parser.parse_args()
    check(args.output.resolve(), args.baseline, tuple(args.size), args.material_diagnostics,
          args.end_distance, args.lighting_variants, args.foliage_variants, args.grass_variants, args.ground_variants,
          args.video, args.canopy_variants, args.rock_variants, args.transmission_variants, args.canopy_visibility,
          args.woodland_variants)
