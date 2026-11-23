"""真实原草与4x MSAA检查距离过渡：近景保持、草高不长大、覆盖平滑归零。"""

import argparse
import json
import os
import sys
from itertools import pairwise
from pathlib import Path

import numpy as np
from panda3d.core import ClockObject, Filename, OrthographicLens, PTALVecBase3f, Shader, Vec3

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT/'src'))

from local_kcd_drive import LocalVegetation, grass_shader

from application import CoastalDrive
from race import GameMode


def check(output):
    output.mkdir(parents=True, exist_ok=False)
    os.environ['LOCALAPPDATA'] = str(output/'user')
    profile = LocalVegetation(output/'assets', ROOT/'logs/local-kcd-original-environment')
    profile.install()
    app = None
    try:
        app = CoastalDrive(smoke=True, output=output, render_size=(640, 320), threading_model='', sync_video=False)
        for name in ('finish-smoke', 'drive-update', 'render-frame-pacing'):
            app.taskMgr.remove(name)
        app.start_game(mode=GameMode.FREE_DRIVE, track='endless')
        app.aspect2d.hide()
        for child in tuple(app.scene.render.getChildren()):
            child.hide()
        app.setBackgroundColor(0, 0, 0)
        original = app.scene.expressway_kit['foliage-shader']
        shaders = {label: grass_shader(original, smooth_distance=enabled)
                   for label, enabled in (('legacy', False), ('smooth', True), ('geometry', True))}
        for label, shader in tuple(shaders.items()):
            fragment = shader.getText(Shader.STFragment)
            fragment = fragment.replace('o_color = vec4(expressway_haze(color.rgb, v_world_position), color.a);',
                                        'o_color=vec4(vec3(1.),color.a);')
            if label == 'geometry':
                fragment = fragment.replace('float foliage_visibility = grass_fade;', 'float foliage_visibility=1.;')
            shaders[label] = Shader.make(Shader.SLGLSL, shader.getText(Shader.STVertex), fragment)
        grass = app.scene.expressway_kit['local-kcd-grass'].copyTo(app.scene.render)
        grass.show()
        grass.setInstanceCount(1)
        grass.setShaderInput('grass_surface_mode', 0., 100)
        for name, corner in zip(('00', '10', '01', '11'), ((-2, -2), (2, -2), (-2, 2), (2, 2)), strict=True):
            values = PTALVecBase3f.emptyArray(80)
            values[0] = Vec3(*corner, 0)
            grass.setShaderInput('grass_floor'+name, values)
        lens = OrthographicLens()
        lens.setFilmSize(5.5, 2.75)
        lens.setNearFar(1, 300)
        app.cam.node().setLens(lens)
        clock = ClockObject.getGlobalClock()
        clock.setMode(ClockObject.MNonRealTime)
        clock.setDt(1/60)
        images, rows = {}, []
        for distance in (100, 140, 155, 170, 185, 200, 210, 220):
            app.camera.setPos(0, -distance, .38)
            app.camera.lookAt(0, 0, .38)
            for label, shader in shaders.items():
                grass.setShader(shader, 2)
                for _ in range(8):
                    app.taskMgr.step()
                app.graphicsEngine.syncFrame()
                assert not shader.getErrorFlag(), label
                picture = app.win.getScreenshot()
                picture.write(Filename.fromOsSpecific(str(output/(label+'-'+str(distance)+'.png'))))
                pixels = np.frombuffer(picture.getRamImageAs('RGB'), dtype=np.uint8).copy()
                images[label, distance] = pixels
                rows.append({'variant': label, 'camera_m': distance, 'mean_rgb8': float(pixels.mean()),
                             'nonblack_channels': int(np.count_nonzero(pixels))})
        near_equal = np.array_equal(images['legacy', 100], images['smooth', 100])
        geometry = []
        for distance in (100, 140, 155, 170, 185, 200, 210):
            pixels = images['geometry', distance].reshape(320, 640, 3)
            y, x = np.where(np.any(pixels > 0, axis=2))
            delta = np.abs(pixels.astype(np.int16)-images['geometry', 100].reshape(320, 640, 3))
            geometry.append({'camera_m': distance,
                'screen_bounds': [int(x.min()), int(y.min()), int(x.max()), int(y.max())],
                'changed_channels_from_100m': int(np.count_nonzero(delta)), 'max_rgb8': int(delta.max())})
        geometry_equal = all(row['screen_bounds'] == geometry[0]['screen_bounds'] for row in geometry)
        coverage = [row['mean_rgb8'] for row in rows if row['variant'] == 'smooth']
        result = {'scope': '正交固定尺度，原4m草格/原图集/原4x MSAA覆盖；0新驾驶步。geometry仅诊断关闭透明度淡出。',
                  'near_pixels_identical': near_equal, 'geometry_screen_bounds_identical_until_210m': geometry_equal,
                  'geometry_readback': geometry, 'samples': rows,
                  'geometry_scope': '正交固定尺度下高度/横向包围盒保持；交叠叶面的深度精度像素差原样列出，不冒称整屏字节保持'}
        (output/'grass-distance-fade.json').write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
        assert near_equal, result
        assert geometry_equal, result
        assert all(a >= b for a, b in pairwise(coverage)), result
        assert coverage[-1] == 0 and coverage[0] > 1, result
        return result
    finally:
        if app is not None:
            app.close_game()
        profile.restore()


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    arguments = parser.parse_args()
    check(arguments.output.resolve())
