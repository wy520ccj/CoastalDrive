"""同一真实GT检查通用树叶遮罩是否误删无底色贴图的车辆投影。"""

import argparse
import json
import sys
from pathlib import Path
from types import SimpleNamespace

import numpy as np
from direct.showbase.ShowBase import ShowBase
from panda3d.core import (
    AmbientLight,
    DirectionalLight,
    Filename,
    Mat4,
    Shader,
    ShaderAttrib,
    Texture,
    Vec3,
    Vec4,
    loadPrcFileData,
)
from simplepbr import Pipeline
from simplepbr._shaderutils import _load_shader_str

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT/'src'))
sys.path.insert(0, str(ROOT/'tools/environment'))

from local_kcd_drive import cutout_shadows

from scene import make_quad
from skins import vehicle_definition
from vehicle_designs import vehicle_design
from vehicle_visual import batch_driving_geometry, load_vehicle


def check(output, wide=False):
    output.mkdir(parents=True, exist_ok=False)
    loadPrcFileData('vehicle-shadow', 'window-type offscreen\nwin-size 960 600\naudio-library-name null\nsync-video false\nthreading-model ')
    app = ShowBase()
    try:
        pipeline = Pipeline(enable_shadows=True, max_lights=1, use_330=True, shadow_bias=.0007)
        app.taskMgr.remove('simplepbr update')
        ambient = AmbientLight('ambient')
        ambient.setColor((.15, .15, .15, 1))
        app.render.setLight(app.render.attachNewNode(ambient))
        sun = app.render.attachNewNode(DirectionalLight('sun'))
        sun.node().setColor((3, 3, 3, 1))
        sun.setPos(-10, -15, 25)
        sun.lookAt(0, 0, 0)
        app.render.setLight(sun)
        scene = SimpleNamespace(sun_path=sun)
        cutout_shadows(scene)
        sun.node().setShadowCaster(True, 1024, 1024)
        sun.node().getLens().setFilmSize(20, 20)
        sun.node().getLens().setNearFar(1, 60)
        if wide:
            sun.node().setShadowCaster(True, 4096, 4096)
            sun.node().getLens().setFilmSize(320, 320)
            sun.node().getLens().setNearFar(10, 300)
            sun.setPos(Vec3(0, 80, 0)+Vec3(-55, -75, 125))
            sun.lookAt(0, 80, 0)
        config = vehicle_design('coastal-gt').config
        car, wheels = load_vehicle(app.render, vehicle_definition('coastal-gt'), config=config)
        batch_driving_geometry(car, wheels)
        car.setZ(config.center_of_mass_height)
        for wheel in wheels:
            wheel.setZ(config.wheel_radius)
        floor = make_quad('floor', Vec3(0, 0, 0), 18, 18, Vec4(.3, .3, .3, 1), 0)
        floor.reparentTo(app.render)
        if wide:
            from environment.expressway_materials import road_shadow_shader

            floor.setShader(road_shadow_shader())
            sky = Texture('unused-nearfield-sky')
            sky.setup2dTexture(1, 1, Texture.TUnsignedByte, Texture.FRgb)
            sky.setRamImage(bytes((0, 0, 0)))
            app.render.setShaderInput('expressway_sky', sky)
            app.render.setShaderInput('expressway_sky_tint', (1., 1., 1.))
            app.render.setShaderInput('expressway_sky_inverse', Mat4.identMat())
        app.camera.setPos(-6, -8, 3)
        app.camera.lookAt(0, 0, .5)
        app.render.setShaderInput('camera_world_position', app.cam.getPos(app.render))
        original = sun.node().getInitialState()
        fragments = {'cutout': original.getAttrib(ShaderAttrib).getShader().getText(Shader.STFragment),
                     'opaque': _load_shader_str('shadow.frag', {'USE_330': True})}
        fragments['alpha_only'] = fragments['cutout'].replace('uniform vec4 p3d_ColorScale;',
            'uniform vec4 p3d_ColorScale;\nuniform vec4 p3d_TexAlphaOnly;').replace(
                'texture2D(p3d_TextureBaseColor, v_texcoord);',
                '(texture2D(p3d_TextureBaseColor, v_texcoord)+p3d_TexAlphaOnly);')
        images = []
        for label, fragment in fragments.items():
            shader = Shader.make(Shader.SLGLSL, _load_shader_str('shadow.vert', {'USE_330': True}), fragment)
            sun.node().setInitialState(original.setAttrib(ShaderAttrib.make(shader), 10))
            for _ in range(12):
                app.graphicsEngine.renderFrame()
            app.graphicsEngine.syncFrame()
            picture = app.win.getScreenshot()
            picture.write(Filename.fromOsSpecific(str(output/(label+'.png'))))
            images.append(np.frombuffer(picture.getRamImageAs('RGB'), dtype=np.uint8).copy())
            assert not shader.getErrorFlag(), label
        rows = []
        for i in (1, 2):
            delta = np.abs(images[i].astype(np.int16)-images[0])
            rows.append({'candidate': list(fragments)[i], 'max_rgb8': int(delta.max()),
                         'changed_channels': int(np.count_nonzero(delta))})
        report = {'scope': '真实GT/四轮与同一平面；仅切换太阳深度片元shader，非产品帧率样本',
                  'differences_from_cutout': rows, 'shadow_bias': pipeline.shadow_bias}
        (output/'shadows.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
        print(report)
    finally:
        app.destroy()


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--wide', action='store_true')
    args = parser.parse_args()
    check(args.output.resolve(), args.wide)
