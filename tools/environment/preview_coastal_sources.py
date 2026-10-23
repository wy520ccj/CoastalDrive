"""用游戏现有晴空与光照审看候选原件；不修改生产场景或物理世界。"""

import argparse
import faulthandler
import io
import json
import os
import random
import struct
import sys
from dataclasses import asdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'src'))

import gltf
from panda3d.core import (
    AlphaTestAttrib,
    DepthWriteAttrib,
    Filename,
    GeomVertexWriter,
    NodePath,
    SceneGraphAnalyzer,
    Texture,
    TransparencyAttrib,
    Vec3,
    Vec4,
)
from PIL import Image

from application import CoastalDrive
from scene import make_quad
from session import Phase

SOURCES = ROOT / 'art/expressway/sources'


def portable_grass(output):
    """仅转换Panda加载器不识别的WebP扩展，源图颜色和遮罩不作美术修改。"""
    data = (SOURCES / 'ez-tree/grass.glb').read_bytes()
    length = struct.unpack_from('<I', data, 12)[0]
    document = json.loads(data[20:20 + length])
    binary = data[28 + length:]
    view = document['bufferViews'][document['images'][0]['bufferView']]
    start = view.get('byteOffset', 0)
    image = Image.open(io.BytesIO(binary[start:start + view['byteLength']]))
    image.save(output / 'grass.png')
    document['buffers'][0]['uri'] = 'grass.bin'
    document['images'] = [{'uri': 'grass.png'}]
    document['textures'][0] = {'source': 0, 'sampler': 0}
    del document['extensionsUsed']
    del document['extensionsRequired']
    material = document['materials'][0]
    material['alphaMode'] = 'MASK'
    material['alphaCutoff'] = .45
    (output / 'grass.bin').write_bytes(binary)
    path = output / 'grass.gltf'
    path.write_text(json.dumps(document), encoding='utf-8')
    return path


def load(path, height=None):
    model = NodePath(gltf.load_model(Filename.fromOsSpecific(str(path))))
    low, high = model.getTightBounds()
    if height is not None:
        scale = height / (high.z - low.z)
        model.setScale(scale)
        model.setZ(-low.z * scale)
    for texture in model.findAllTextures():
        texture.setMinfilter(Texture.FTLinearMipmapLinear)
        texture.setAnisotropicDegree(4)
    return model


def preview(output):
    output.mkdir(parents=True, exist_ok=False)
    os.environ['LOCALAPPDATA'] = str(output / 'user')
    faulthandler.dump_traceback_later(45, repeat=True)
    app = CoastalDrive(smoke=True, output=output, render_size=(1440, 810), threading_model='')
    app.taskMgr.remove('finish-smoke')
    app.taskMgr.remove('drive-update')
    rows = []
    try:
        app.open_career()
        app.career_action('start', 'first-drive')
        while app.session.phase == Phase.COUNTDOWN:
            app.session.tick()
        app.refresh_panel()
        app.apply_scene(app.session.current, 0.)
        app.aspect2d.hide()
        original = asdict(app.session.current)
        scene = app.scene
        # 保留同一光源、反射与天空；单件预览不混入旧草木，也不移动任何碰撞体。
        retained = {scene.sky, scene.ambient_path, scene.sun_path, scene.rail_sun_path}
        for child in scene.render.getChildren():
            if child not in retained:
                child.hide()
        stage = scene.render.attachNewNode('source-review-only')
        ground = make_quad('review-ground', Vec3(0, 0, 0), 300, 300,
                           Vec4(.23, .28, .10, 1), z=-.02)
        ground.reparentTo(stage)
        models = stage.attachNewNode('review-models')

        def capture(name, position, target, **details):
            app.camera.setPos(*position)
            app.camera.lookAt(*target)
            scene.sky.setPos(app.camera.getPos())
            scene.update_lighting(app.camera.getPos())
            for _ in range(8):
                app.taskMgr.step()
            app.graphicsEngine.syncFrame()
            assert asdict(app.session.current) == original
            assert not scene.expressway_kit['foliage-shader'].getErrorFlag()
            assert not scene.expressway_kit['distance-shader'].getErrorFlag()
            graph = SceneGraphAnalyzer()
            graph.addNode(models.node())
            app.win.getScreenshot().write(Filename.fromOsSpecific(str(output / (name + '.png'))))
            rows.append({'file': name + '.png', 'triangles': graph.getNumTris(), **details})

        for level in range(3):
            tree = load(SOURCES / f'ez-tree/lods/tree_LOD{level}.glb', height=10.)
            tree.reparentTo(models)
            tree.setShader(scene.expressway_kit['foliage-shader'], 2)
            tree.setShaderInput('foliage_alpha_cutoff', .45)
            capture(f'01-oak-lod{level}', (13, -19, 7), (0, 0, 5), height_m=10.)
            tree.removeNode()

        grass = load(portable_grass(output))
        grass.setShader(scene.expressway_kit['foliage-shader'], 2)
        grass.setShaderInput('foliage_alpha_cutoff', .45)
        grass.setTransparency(TransparencyAttrib.MNone, 2)
        grass.setAttrib(AlphaTestAttrib.make(AlphaTestAttrib.MGreaterEqual, .45), 2)
        grass.setAttrib(DepthWriteAttrib.make(DepthWriteAttrib.MOn), 2)
        # 交叉草片的几何法线会让同簇各面一黑一亮；按草甸整体的向上法线受光。
        print('PREPARE GRASS NORMALS', flush=True)
        for part in grass.findAllMatches('**/+GeomNode'):
            normal = part.getRelativeVector(grass, Vec3(0, 0, 1)).normalized()
            for index in range(part.node().getNumGeoms()):
                data = part.node().modifyGeom(index).modifyVertexData()
                writer = GeomVertexWriter(data, 'normal')
                for _ in range(data.getNumRows()):
                    writer.setData3f(normal)
                del writer
        print('PREPARE GRASS PATCH', flush=True)
        # 作者原件为中性灰草图集，颜色由实例提供；采用低饱和黄绿色。
        grass.setColorScale(.26, .34, .12, 1)
        rng = random.Random(24)
        for row in range(32):
            for column in range(32):
                plant = grass.copyTo(models)
                plant.setPos((column - 15.5) * .125 + rng.uniform(-.04, .04),
                             (row - 15.5) * .125 + rng.uniform(-.04, .04), 0)
                plant.setH(rng.uniform(0, 360))
                plant.setScale(.20, .20, rng.uniform(.075, .115))
        capture('02-grass-cover', (3.8, -5.5, 1.65), (0, 0, .10), area_m2=16,
                plants=1024, height_m=[.15, .23])
        capture('03-grass-close', (1.2, -1.6, .55), (0, 0, .1), area_m2=16)
        print('GRASS CAPTURED', flush=True)
        models.getChildren().detach()

        for asset, position, target in (
            ('coastal_cliff_01', (55, -60, 21), (0, 0, 3)),
            ('coast_rocks_01', (42, -51, 21), (0, 3, 0)),
        ):
            rock = load(SOURCES / f'coastal-scans/{asset}/{asset}_2k.gltf')
            rock.reparentTo(models)
            capture('04-' + asset, position, target, scale='source metres')
            rock.removeNode()
        report = {'scope': '候选原件的游戏光照离屏预览；无新驾驶拍；非已实现景观或人工验收',
                  'snapshot_tick': original['tick'], 'captures': rows}
        (output / 'summary.json').write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n',
                                            encoding='utf-8')
        print('SOURCE PREVIEW', output)
    finally:
        faulthandler.cancel_dump_traceback_later()
        app.close_game()


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    preview(args.output.resolve())
