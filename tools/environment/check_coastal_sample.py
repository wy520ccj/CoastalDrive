"""在真实起步后的同一世界对照沿海完整样板；候选只挂显示节点，不改生产场景。"""

import argparse
import faulthandler
import json
import math
import os
import random
import sys
from dataclasses import asdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'src'))

import gltf
from kcd_local_assets import load_local, model
from panda3d.core import (
    AlphaTestAttrib,
    DepthWriteAttrib,
    Filename,
    LODNode,
    NodePath,
    SceneGraphAnalyzer,
    Shader,
    ShaderAttrib,
    Texture,
    TransparencyAttrib,
)

from application import CoastalDrive
from environment.expressway_route import terrain_point
from environment.expressway_vegetation import ground_point
from environment.surface_mesh import surface_mesh
from session import Phase
from vehicle_designs import vehicle_design
from vehicle_workspace import WorkspaceVehicle

CANDIDATES = ROOT / 'art/expressway/candidates'


def source(path):
    model = NodePath(gltf.load_model(Filename.fromOsSpecific(str(path))))
    for texture in model.findAllTextures():
        texture.setMinfilter(Texture.FTLinearMipmapLinear)
        texture.setAnisotropicDegree(4)
    for part in model.findAllMatches('**/+GeomNode'):
        for index, state in enumerate(part.node().getGeomStates()):
            state = state.removeAttrib(AlphaTestAttrib.getClassType())
            state = state.setAttrib(TransparencyAttrib.make(TransparencyAttrib.MNone))
            state = state.setAttrib(DepthWriteAttrib.make(DepthWriteAttrib.MOn))
            part.node().setGeomState(index, state)
    return model


def distance_model(model, names, ranges, center):
    lod = LODNode(names[0] + '-distance')
    lod.setCenter(center)
    root = NodePath(lod)
    for name, switch in zip(names, ranges, strict=True):
        part = model.find('**/' + name)
        if part.isEmpty():
            raise ValueError('候选缺少模型：' + name)
        part.copyTo(root)
        lod.addSwitch(*switch)
    return root


def prepare_sample(scene):
    kit, seed = scene.expressway_kit, scene.base.session.simulation.seed
    stage = scene.render.attachNewNode('coastal-composition-candidate')
    # 仅替换本次显示中的旧草木；权威世界、碰撞树干和道路均保持。
    for part in tuple(scene.render.findAllMatches('**/+LODNode')):
        if part.getName() in ('broadleaf-a', 'broadleaf-b', 'fine-shrubs', 'source-grass'):
            part.hide()
    for index, root in scene.segment_nodes.items():
        if not -1 <= index <= 1:
            continue
        for part in root.findAllMatches('**/+GeomNode'):
            for number in reversed(range(part.node().getNumGeoms())):
                shader = part.node().getGeomState(number).getAttrib(ShaderAttrib)
                if shader is not None and shader.getShader() == kit['route-terrain-shader']:
                    part.node().removeGeom(number)
    trees, grasses, ground_texture = load_local(ROOT / 'logs/play-repair-kcd-local/assets', kit['foliage-shader'])
    # 样板阴影也按图集Alpha裁切，不能将整张枝叶矩形投到草地上。
    from simplepbr._shaderutils import _load_shader_str

    defines = {'USE_330': True}
    vertex = _load_shader_str('shadow.vert', defines.copy())
    fragment = _load_shader_str('shadow.frag', defines.copy()).replace(
        '#ifdef USE_330\n    o_color = base_color;',
        'if (base_color.a < .25) discard;\n#ifdef USE_330\n    o_color = base_color;')
    light = scene.sun_path.node()
    light.setInitialState(light.getInitialState().setAttrib(
        ShaderAttrib.make(Shader.make(Shader.SLGLSL, vertex, fragment)), 10))
    rng = random.Random(2402)
    forest = []
    # 图24左侧林缘沿坡形成整片，错列只用于林带内部，右侧保留看海开口。
    for row, lateral in enumerate((-24, -34, -46, -61, -80)):
        for n in range(23):
            s = -15 + n * 14 + row * 5 + rng.uniform(-2.5, 2.5)
            d = lateral + rng.uniform(-2, 2)
            size = rng.uniform(1.05, 1.55)
            forest.append((d, s, size))
    forest.extend(((27, 55, 1.35), (36, 61, 1.0), (27, 157, 1.55), (38, 167, 1.1)))
    for d, s, size in forest:
        node = trees[rng.randrange(len(trees))].copyTo(stage)
        node.setPos(terrain_point(None, d, s, seed))
        node.setScale(size * .62)
        node.setH(rng.uniform(0, 360))
    print('SAMPLE FOREST', len(forest), flush=True)

    for side in (-1, 1):
        vertices, normals, colors, uv, faces = [], [], [], [], []
        columns = [side * n for n in (8.5, 10, 12, 16, 20, 24, 28, 32, 35, 40, 48, 60, 75, 95, 120)]
        columns.sort()
        for s in range(-200, 401, 4):
            for d in columns:
                p = terrain_point(None, d, s, seed)
                dx = terrain_point(None, d + .1, s, seed) - terrain_point(None, d - .1, s, seed)
                dy = terrain_point(None, d, s + .1, seed) - terrain_point(None, d, s - .1, seed)
                normal = dx.cross(dy).normalized()
                vertices.append(tuple(p))
                normals.append(normal)
                variation = .9 + .13 * math.sin(d * .09 + s * .035) + .06 * math.sin(s * .12)
                colors.append((.29 * variation, .35 * variation, .20 * variation,
                               max(0, min(1, (1 - normal.z) * 5)) if side < 0 else 0))
                uv.append((d, s))
        width = len(columns)
        for row in range(150):
            for col in range(width - 1):
                a = row * width + col
                faces.extend(((a, a + 1, a + width + 1), (a, a + width + 1, a + width)))
        ground = surface_mesh('sample-continuous-ground', vertices, faces, normals, colors, uv)
        ground.setTexture(ground_texture)
        ground.setMaterial(kit['surface-material'])
        ground.setShader(kit['route-terrain-shader'], 2)
        ground.setShaderInput('expressway_rock', kit['rock'])
        ground.reparentTo(stage)

    patches = 0
    for side in (-1, 1):
        for s in range(-8, 133, 4):
            for d in (11, 15, 19, 23, 27, 31):
                d *= side
                points, normals, colors, uv, faces = [], [], [], [], []
                for row in range(8):
                    for col in range(8):
                        mesh, texture = grasses[rng.randrange(len(grasses))]
                        x = d + (col - 3.5) * .5 + rng.uniform(-.1, .1)
                        y = s + (row - 3.5) * .5 + rng.uniform(-.1, .1)
                        height = ground_point(None, x, y, seed).z
                        angle, scale = rng.uniform(0, math.tau), rng.uniform(.45, .65)
                        co, si = math.cos(angle), math.sin(angle)
                        offset = len(points)
                        for p, n, t in zip(mesh['points'], mesh['normals'], mesh['uv'], strict=True):
                            points.append((x + (p[0]*co-p[1]*si)*scale,
                                           y + (p[0]*si+p[1]*co)*scale, height + p[2]*scale))
                            normals.append((n[0]*co-n[1]*si, n[0]*si+n[1]*co, n[2]))
                            shade = .8 + .2 * max(0, min(1, p[2] / .2))
                            colors.append((shade, shade, shade, 1))
                            uv.append(t)
                        faces.extend(tuple(offset + i for i in face) for face in mesh['faces'])
                batch = {'points': points, 'normals': normals, 'uv': uv, 'faces': faces}
                patch = model('kcd-local-meadow', batch, texture, kit['foliage-shader'])
                patch.reparentTo(stage)
                patches += 1
            if s % 24 == 16:
                print('KCD MEADOW ROW', side, s, flush=True)
    print('SAMPLE MEADOW', patches, flush=True)

    rocks_source = source(CANDIDATES / 'coastal-rocks/coastal-rocks.glb')
    for label, center, ranges, placements in (
        ('cliff', (0, 0, 4), ((100, 0), (300, 100), (900, 300)),
         ((-49, 70, 3, 90), (-57, 163, 5, 96), (-67, 255, 7, 92))),
        ('shore', (0, 0, 0), ((100, 0), (300, 100), (900, 300)),
         ((65, 72, -2.5, 90), (68, 138, -2.6, 72), (65, 200, -2.5, 100))),
    ):
        rock = distance_model(rocks_source, tuple(f'{label}-lod{i}' for i in range(3)), ranges, center)
        for x, y, z, heading in placements:
            node = rock.copyTo(stage)
            node.setPos(x, y, z)
            node.setH(heading)
    return stage, {'trees': len(forest), 'grass_patches': patches, 'rock_sections': 6}


def check(output, size):
    output.mkdir(parents=True, exist_ok=False)
    os.environ['LOCALAPPDATA'] = str(output / 'user')
    faulthandler.dump_traceback_later(90, repeat=True)
    app = CoastalDrive(smoke=True, output=output, render_size=size, threading_model='',
                       workspace_vehicle=WorkspaceVehicle('porsche-930', vehicle_design('porsche-930').config))
    app.taskMgr.remove('finish-smoke')
    app.taskMgr.remove('drive-update')
    captures = []
    try:
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
        app.refresh_panel()
        app.apply_scene(app.session.current, 0.)
        original = asdict(app.session.current)
        app.hud.resize(app.getAspectRatio())
        app.hud.update(app.session.current, app.session.race.snapshot, app.session.highway.snapshot,
                       track=app.session.simulation.track, countdown='', notice='', driving_mode=app.session.driving_mode)

        def capture(name):
            for _ in range(8):
                app.taskMgr.step()
            app.graphicsEngine.syncFrame()
            assert asdict(app.session.current) == original
            assert not app.scene.expressway_kit['foliage-shader'].getErrorFlag()
            app.win.getScreenshot().write(Filename.fromOsSpecific(str(output / (name + '.png'))))
            captures.append({'file': name + '.png', 'camera': list(app.camera.getPos())})

        capture('00-baseline-driving')
        stage, counts = prepare_sample(app.scene)
        capture('01-sample-driving')
        app.aspect2d.hide()
        for name, position, target in (
            ('02-verge', (-7, 18, 1.5), (-18, 33, -.1)),
            ('03-tree-crown', (-8, 18, 4), (-25, 35, 5)),
            ('04-coast', (8, 22, 3), (65, 85, -2)),
            ('05-mid-distance', (0, 88, 4), (0, 180, 4)),
        ):
            app.camera.setPos(*position)
            app.camera.lookAt(*target)
            app.scene.sky.setPos(app.camera.getPos())
            app.scene.update_lighting(app.camera.getPos())
            capture(name)
        graph = SceneGraphAnalyzer()
        graph.addNode(stage.node())
        report = {'scope': 'KCD2本机原始橡树/草网格及图集本地试用；240真实新驾驶步后固定快照对照；非正式运行版或性能/人工验收',
                  'new_driving_steps': app.session.current.tick - first, 'snapshot': original,
                  'size': size, 'counts': counts, 'captures': captures,
                  'candidate_triangles_all_lods': graph.getNumTris()}
        (output / 'summary.json').write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
        print('COASTAL SAMPLE CAPTURED', output, flush=True)
    finally:
        faulthandler.cancel_dump_traceback_later()
        app.close_game()


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--size', nargs=2, type=int, default=(1440, 810))
    args = parser.parse_args()
    check(args.output.resolve(), tuple(args.size))
