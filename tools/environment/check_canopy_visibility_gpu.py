"""实际GPU检查树冠遮蔽只调天空填光，关闭后轮廓/底色和阴影深度保持。"""

import argparse
import hashlib
import json
import os
import sys
from pathlib import Path

import numpy as np
from panda3d.core import (
    ClockObject,
    Filename,
    GeomVertexData,
    GeomVertexWriter,
    OrthographicLens,
    Shader,
    ShaderAttrib,
    Texture,
    Vec3,
)

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'src'))

from bake_kcd_canopy_visibility import bake
from kcd_local_assets import load_local
from local_kcd_drive import LocalVegetation, tree_shader

from application import CoastalDrive
from race import GameMode


def check(output):
    output.mkdir(parents=True, exist_ok=False)
    os.environ['LOCALAPPDATA'] = str(output / 'user')
    profile = LocalVegetation(output / 'assets', ROOT / 'logs/local-kcd-original-environment', canopy_visibility=None)
    profile.install()
    app = None
    try:
        app = CoastalDrive(smoke=True, output=output, render_size=(640, 480), threading_model='', sync_video=False)
        for name in ('finish-smoke', 'drive-update', 'render-frame-pacing'):
            app.taskMgr.remove(name)
        app.start_game(mode=GameMode.FREE_DRIVE, track='endless')
        app.aspect2d.hide()
        for child in tuple(app.scene.render.getChildren()):
            child.hide()
        bake('a', output / 'visibility', output / 'assets/oak.png', 24)
        source = app.scene.expressway_kit['local-kcd-trees'][0].getChild(0).getShader()
        trees, _, _ = load_local(output / 'baked-assets', source, distance_lods=True, tree_letters='a',
                                 canopy_visibility=output / 'visibility')
        tree = trees[0].copyTo(app.scene.render)
        tree.show()
        tree.node().setFadeTime(0.)
        center = float(tree.getTag('source-height')) * .5
        lens = OrthographicLens()
        lens.setFilmSize(26, 19.5)
        lens.setNearFar(1, 300)
        app.cam.node().setLens(lens)
        app.camera.setPos(0, -40, center)
        app.camera.lookAt(0, 0, center)
        app.scene.update_lighting(Vec3(0, 0, 0))
        clock = ClockObject.getGlobalClock()
        clock.setMode(ClockObject.MNonRealTime)
        clock.setDt(1 / 60)
        data = []
        for path in tree.findAllMatches('**/+GeomNode'):
            geom = path.node().modifyGeom(0)
            original = geom.getVertexData()
            white = GeomVertexData(original)
            writer = GeomVertexWriter(white, 'color')
            for _ in range(white.getNumRows()):
                writer.setData4f(1, 1, 1, 1)
            data.append((geom, original, white))

        def capture():
            for _ in range(8):
                app.taskMgr.step()
            app.graphicsEngine.syncFrame()
            texture = app.scene.sun_path.node().getShadowBuffer(app.win.getGsg()).getTexture()
            assert app.graphicsEngine.extractTextureData(texture, app.win.getGsg())
            depth = bytes(texture.getRamImage())
            assert depth
            picture = app.win.getScreenshot()
            pixels = np.frombuffer(picture.getRamImageAs('RGB'), dtype=np.uint8).copy()
            return picture, pixels, hashlib.sha256(depth).hexdigest()

        report = []
        for level in range(3):
            tree.node().forceSwitch(level)
            rows, pixels = [], []
            for label, strength in (('white', 0.), ('mask-disabled', 0.), ('mask-enabled', .7)):
                for geom, original, white in data:
                    geom.setVertexData(white if label == 'white' else original)
                app.scene.render.setShaderInput('local_canopy_occlusion', strength)
                picture, rgb, shadow = capture()
                rows.append({'variant': label, 'shadow_sha256': shadow})
                pixels.append(rgb)
                if level == 0:
                    picture.write(Filename.fromOsSpecific(str(output / (label + '.png'))))
            assert np.array_equal(pixels[0], pixels[1]), '遮蔽关闭后不应改变底色或轮廓'
            assert len({row['shadow_sha256'] for row in rows}) == 1, '遮蔽不应改变投影深度'
            difference = float(np.abs(pixels[1].astype(float) - pixels[2]).mean())
            assert difference > .01, '树冠天空遮蔽未实际生效'
            sky_rows, sky_pixels = [], []
            for strength in (0., 1.):
                tree.setShaderInput('local_sky_transmission', strength, 100)
                picture, rgb, shadow = capture()
                sky_rows.append({'strength': strength, 'shadow_sha256': shadow})
                sky_pixels.append(rgb)
                if level == 0:
                    picture.write(Filename.fromOsSpecific(str(output / ('sky-transmission-' + str(int(strength)) + '.png'))))
            assert len({row['shadow_sha256'] for row in [*rows, *sky_rows]}) == 1
            sky_change = float(sky_pixels[1].mean()-sky_pixels[0].mean())
            assert sky_change > .01, '背面天空透光没有实际作用于原树'
            states = []
            for path in tree.findAllMatches('**/+GeomNode'):
                for number in range(path.node().getNumGeoms()):
                    state = path.node().getGeomState(number)
                    attrib = path.getNetState().compose(state).getAttrib(ShaderAttrib)
                    shader = attrib.getShader()
                    fragment = shader.getText(Shader.STFragment)
                    final = 'o_color = vec4(expressway_haze(color.rgb, v_world_position), color.a);'
                    assert final in fragment
                    fragment = fragment.replace(final, '''o_color=vec4(abs(
                        local_opposite_sky(world_normal,local_sky_irradiance)
                        -max(irradiance_from_sh(-world_normal),0.)),2.);''')
                    debug = Shader.make(Shader.SLGLSL, shader.getText(Shader.STVertex), fragment)
                    # 仅覆盖可见材质，优先级低于原太阳相机的遮罩程序。
                    path.node().setGeomState(number, state.setAttrib(attrib.setShader(debug, 2), 2))
                    states.append((path, number, state))
            _, _, shadow = capture()
            assert shadow == sky_rows[0]['shadow_sha256']
            hdr = app.pipeline._post_process_quad.getShaderInput('tex').getTexture()
            assert app.graphicsEngine.extractTextureData(hdr, app.win.getGsg())
            dtype = {2: np.float16, 4: np.float32}[hdr.getComponentWidth()]
            raw = np.frombuffer(hdr.getRamImageAs('RGBA'), dtype=dtype).reshape(-1, 4)
            # HDR alpha标记只选出实际原树片元，不能把显示区域的清屏背景纳入误差。
            tree_pixels = raw[:, 3] > 1.5
            assert np.count_nonzero(tree_pixels) > 100
            sh_error = float(np.max(raw[tree_pixels, :3]))
            assert sh_error < 1e-5, f'复用SH与原反方向采样的最大误差：{sh_error}'
            for path, number, state in states:
                path.node().setGeomState(number, state)
            black = Texture('zero-subsurface-mask')
            black.setup2dTexture(1, 1, Texture.TUnsignedByte, Texture.FRgb)
            black.setRamImage(bytes(3))
            tree.setShaderInput('local_transmission', black, 100)
            zero_pixels = []
            for strength in (0., 1.):
                tree.setShaderInput('local_sky_transmission', strength, 100)
                _, rgb, shadow = capture()
                assert shadow == sky_rows[0]['shadow_sha256']
                zero_pixels.append(rgb)
            assert np.array_equal(*zero_pixels), '透光遮罩为0时不应给不透光材质统一加亮'
            tree.clearShaderInput('local_transmission')
            tree.setShaderInput('local_sky_transmission', 0., 100)
            filter_pixels, filter_depths, filter_states = [], [], []
            for path in tree.findAllMatches('**/+GeomNode'):
                for number in range(path.node().getNumGeoms()):
                    state = path.node().getGeomState(number)
                    attrib = path.getNetState().compose(state).getAttrib(ShaderAttrib)
                    filter_states.append((path, number, state, attrib))
            unfiltered = tree_shader(app.scene.expressway_kit['foliage-shader'], filtered_shadows=False)
            for enabled in (True, False, True):
                for path, number, state, attrib in filter_states:
                    path.node().setGeomState(number, state if enabled else
                        state.setAttrib(attrib.setShader(unfiltered, 2), 2))
                picture, rgb, shadow = capture()
                filter_pixels.append(rgb)
                filter_depths.append(shadow)
                if level == 0:
                    picture.write(Filename.fromOsSpecific(str(output / ('filtered-shadow-'+str(int(enabled))+'.png'))))
            for path, number, state, _attrib in filter_states:
                path.node().setGeomState(number, state)
            assert np.array_equal(filter_pixels[0], filter_pixels[2]), '恢复过滤后画面应可重复'
            assert len(set(filter_depths)) == 1 and filter_depths[0] == rows[0]['shadow_sha256']
            filter_change = float(np.abs(filter_pixels[0].astype(float)-filter_pixels[1]).mean())
            assert filter_change > .01, '木本阴影过滤没有作用于原树'
            tree.hide()
            _, _, empty_shadow = capture()
            tree.show()
            assert empty_shadow != rows[0]['shadow_sha256'], '当前阴影图没有实际包含原树'
            report.append({'lod': level, 'disabled_pixels_equal_white': True, 'ambient_change_rgb8': difference,
                           'shadow_differs_from_empty': True, 'variants': rows, 'sky_transmission': sky_rows,
                           'sky_transmission_change_rgb8_mean': sky_change,
                           'opposite_sh_reuse_max_linear_error': sh_error,
                           'zero_transmission_mask_pixels_identical': True,
                           'shadow_filter_change_rgb8_mean': filter_change,
                           'shadow_filter_preserves_source_depth': True,
                           'shadow_filter_repeat_pixels_identical': True})
        result = {'scope': '同一实际原树/三档LOD的GPU与太阳深度图，60Hz技术采样/0新驾驶步', 'lods': report}
        (output / 'canopy-gpu.json').write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
        return result
    finally:
        if app is not None:
            app.close_game()
        profile.restore()


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    arguments = parser.parse_args()
    print(json.dumps(check(arguments.output.resolve()), ensure_ascii=False))
