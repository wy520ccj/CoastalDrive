"""真实路段的原生合批分项计时；只构建离开场景的节点，不开启驾驶窗口。"""

import argparse
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT/'src'))
sys.path.insert(0, str(ROOT/'tools/environment'))

from local_kcd_drive import LocalVegetation
from panda3d.core import (
    AmbientLight,
    DirectionalLight,
    Loader,
    LoaderOptions,
    LODNode,
    NodePath,
    TexturePool,
)

from career_courses import CareerCourse
from environment.surface_mesh import flatten_steps
from scene import Scene


class AssetLoader:
    def loadModel(self, path):
        return NodePath(Loader.getGlobalPtr().loadSync(path, LoaderOptions()))

    def loadTexture(self, path):
        return TexturePool.loadTexture(path)


def geometry(root):
    result = []
    for path in root.findAllMatches('**/+GeomNode'):
        for geom in path.node().getGeoms():
            data = geom.getVertexData()
            result.append((path.getMat(root), path.getState(root), data.getFormat(),
                           tuple(bytes(array.getHandle().getData()) for array in data.getArrays()),
                           tuple((p.getPrimitiveType(), p.isIndexed(), p.getIndexType(),
                                  tuple(p.getVertex(i) for i in range(p.getNumVertices())))
                                 for p in geom.getPrimitives())))
    return result


def check(output, indices):
    output.mkdir(parents=True, exist_ok=False)
    holder = NodePath('detached-check')
    templates = holder.attachNewNode('templates')
    scene = Scene.__new__(Scene)
    scene.ambient_path = templates.attachNewNode(AmbientLight('ambient'))
    scene.rail_sun_path = templates.attachNewNode(DirectionalLight('rail-sun'))
    trees = [scene.load_model('nature/tree_pineTall'+variant+'.glb') for variant in ('A', 'B')]
    profile = LocalVegetation(ROOT/'logs/local-kcd-drive/assets', ROOT/'logs/local-kcd-original-environment')
    profile.install()
    rows = []
    try:
        kit = profile.load_kit(AssetLoader(), templates, trees)
        for index in indices:
            root = NodePath('segment-'+str(index))
            work = profile.segment(root, index, 0, kit, scene.stabilize_rail, CareerCourse('ridge-club'))
            count = 0
            try:
                for phase in work:
                    count += phase == 'trees'
                    if count == 8:
                        break
                else:
                    raise RuntimeError('未取得真实路段合批前节点')
            finally:
                work.close()
            batch = root.attachNewNode('road-batch')
            for child in list(root.getChildren()):
                if child != batch and not isinstance(child.node(), LODNode):
                    child.reparentTo(batch)
            copies = [batch.copyTo(holder) for _ in range(2)]
            for path in copies:
                path.clearModelNodes()
            start = time.perf_counter()
            copies[0].flattenStrong()
            row = {'index': index, 'original_ms': (time.perf_counter()-start)*1000, 'stages_ms': {}}
            steps = flatten_steps(copies[1])
            while True:
                start = time.perf_counter()
                try:
                    name = next(steps)
                except StopIteration:
                    break
                row['stages_ms'][name] = (time.perf_counter()-start)*1000
            row['identical'] = geometry(copies[0]) == geometry(copies[1])
            row['geoms'] = len(geometry(copies[0]))
            rows.append(row)
            print(row, flush=True)
            for path in copies:
                path.removeNode()
            root.removeNode()
        report = {'passed': all(row['identical'] for row in rows), 'runs': rows,
                  'scope': '真实原资源/1m路网的离场节点，原生flattenStrong对照当前产品分项；非正常帧时或完整场景GPU验收。',
                  'reference': 'https://github.com/panda3d/panda3d/blob/v1.10.16/panda/src/pgraph/nodePath.cxx#L5211-L5222'}
        (output/'summary.json').write_text(json.dumps(report, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
        assert report['passed'], report
    finally:
        profile.restore()
        holder.removeNode()
        templates.removeNode()


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--indices', type=int, nargs='+', default=(7, 8, 10))
    args = parser.parse_args()
    check(args.output.resolve(), args.indices)
