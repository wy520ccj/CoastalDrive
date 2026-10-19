"""实际BAM几何净距与固定路段渲染；不移动物理车辆或改变交通。"""

import argparse
import hashlib
import json
import math
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT/'src'))

from panda3d.core import Filename, GeomVertexReader, NodePath, Vec3

from application import CoastalDrive
from environment.expressway_route import anchor, build_segment, positions, sample
from highway_curve import HighwayCurve
from lab_records import model_fingerprint
from lab_runtime import runtime_fingerprint

SMALL_SIGNS = {'speed-limit', 'curve-left', 'curve-right', 'hill-warning', 'wind-warning'}


def source_hashes():
    result = model_fingerprint()
    for name in ('src/environment/expressway_route.py', 'src/environment/expressway_signs.py',
                 'tools/environment/soundwall_sign_check.py'):
        result[name] = hashlib.sha256((ROOT/name).read_bytes()).hexdigest()
    for name in (*sorted(SMALL_SIGNS), 'soundwall'):
        path = f'assets/game/expressway/{name}.bam'
        result[path] = hashlib.sha256((ROOT/path).read_bytes()).hexdigest()
    return result


def lateral_extent(node, parent, right):
    values = []
    for path in node.findAllMatches('**/+GeomNode'):
        for geom in path.node().getGeoms():
            reader = GeomVertexReader(geom.getVertexData(), 'vertex')
            while not reader.isAtEnd():
                values.append(parent.getRelativePoint(path, tuple(reader.getData3f())).dot(right))
    return min(values), max(values)


def geometry(kit):
    root = NodePath('read-only-model-clearance')
    results = []
    try:
        for seed in (0, 17, 23):
            for shape in ('straight', 'curve', 'hills'):
                curve = None if shape == 'straight' else HighwayCurve(seed, hills=shape == 'hills')
                items = [item for index in range(80) for item in positions(index, seed, curve)]
                walls = [item for item in items if item[0] == 'soundwall']
                for model, d, s, heading in items:
                    if model not in SMALL_SIGNS:
                        continue
                    near = [wall for wall in walls if wall[2]-.3 <= s <= wall[2]+4.3]
                    if not near:
                        continue
                    pose = curve.sample(s) if curve else None
                    angle = math.radians(pose.heading if pose else 0.)
                    right = Vec3(math.cos(angle), math.sin(angle), 0.)
                    sign = kit[model].copyTo(root)
                    sign.setPos(sample(curve, s, d))
                    sign.setH(heading+(pose.heading if pose else 0.))
                    _, maximum = lateral_extent(sign, root, right)
                    gap = math.inf
                    for _, wd, ws, wh in near:
                        wall = kit['soundwall'].copyTo(root)
                        wall.setPos(sample(curve, ws, wd))
                        wp = curve.sample(ws) if curve else None
                        wall.setHpr(wh+(wp.heading if wp else 0.), wp.grade if wp else 0., 0.)
                        minimum, _ = lateral_extent(wall, root, right)
                        gap = min(gap, minimum-maximum)
                        wall.removeNode()
                    sign.removeNode()
                    results.append({'seed': seed, 'shape': shape, 'model': model, 's': s, 'd': d, 'gap_m': gap})
        return results
    finally:
        root.removeNode()


def check(output, phase):
    output.mkdir(parents=True, exist_ok=False)
    source, runtime = source_hashes(), runtime_fingerprint()
    app = CoastalDrive(smoke=True, output=output, seed=23, track='endless', road_shape='hills')
    app.taskMgr.remove('finish-smoke')
    app.taskMgr.remove('drive-update')
    try:
        rows = geometry(app.scene.expressway_kit)
        curve = app.session.simulation.road.curve
        root = app.scene.render.attachNewNode('read-only-2050m-segment')
        build_segment(root, 10, 23, app.scene.expressway_kit, app.scene.stabilize_rail, curve)
        root.setPos(*anchor(curve, 10))
        camera = sample(curve, 2028., 3.5)+Vec3(0, 0, 2.)
        look = sample(curve, 2050., 9.6)+Vec3(0, 0, 1.8)
        app.camera.setPos(camera)
        app.camera.lookAt(look)
        app.camLens.setFov(42)
        app.scene.sky.setPos(camera)
        app.scene.update_lighting(camera)
        app.aspect2d.hide()
        before = app.session.simulation.snapshot()
        bodies = app.session.simulation._world.getNumRigidBodies()
        for _ in range(8):
            app.taskMgr.step()
        app.graphicsEngine.syncFrame()
        assert app.session.simulation.snapshot() == before and app.session.simulation._world.getNumRigidBodies() == bodies
        assert app.win.getScreenshot().write(Filename.fromOsSpecific(str(output/'2050m.png')))
        target = next(row for row in rows if row['seed'] == 23 and row['shape'] == 'hills' and row['s'] == 2050)
        passed = all(row['gap_m'] >= .2 for row in rows)
        summary = {'phase': phase, 'geometry_passed': passed, 'cases': rows, 'target': target,
                   'camera': tuple(camera), 'look_at': tuple(look), 'physics_unchanged': True,
                   'source_start': source, 'source_end': source_hashes(), 'runtime_start': runtime,
                   'runtime_end': runtime_fingerprint(), 'scope': '真实游戏段和BAM的只读静态渲染/完整顶点投影，不是新驾驶'}
        (output/'summary.json').write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding='utf-8')
        assert source == source_hashes() and runtime == runtime_fingerprint()
        assert (not passed) if phase == 'before' else passed
        print(json.dumps({'phase': phase, 'pairs': len(rows), 'target_gap_m': target['gap_m'], 'geometry_passed': passed}))
    finally:
        app.aspect2d.show()
        app.close_game()


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--phase', choices=('before', 'after'), required=True)
    args = parser.parse_args()
    check(args.output.resolve(), args.phase)
