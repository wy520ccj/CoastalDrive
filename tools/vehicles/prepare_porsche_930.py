"""将有来源的930完整车身和四轮打包为道路、车库共用资产。"""

import hashlib
import json
from pathlib import Path

import gltf
from panda3d.core import Filename, GeomNode, MaterialAttrib, NodePath, loadPrcFileData

ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT/'art/vehicles/porsche_930.glb'
OUTPUT = ROOT/'assets/game/vehicles/porsche_930.bam'
WHEELS = ('wheel-front-left', 'wheel-front-right', 'wheel-back-left', 'wheel-back-right')


def prepare():
    loadPrcFileData('', 'bam-texture-mode rawdata')
    source = NodePath(gltf.load_model(Filename.fromOsSpecific(str(SOURCE))))
    root = NodePath('porsche-930')
    root.setTag('authored-proportions', 'wheel-hubs')
    wheels = {name: root.attachNewNode(name) for name in WHEELS}
    triangles = 0
    for part in source.findAllMatches('**/+GeomNode'):
        ancestors = {node.getName() for node in part.getAncestors()}
        parent = next((node for name, node in wheels.items() if name in ancestors), root)
        for index, geom in enumerate(part.node().getGeoms()):
            state = part.node().getGeomState(index)
            material = state.getAttrib(MaterialAttrib).getMaterial()
            node = GeomNode('paint' if material.getName() == 'Body Paint' else part.getName())
            node.addGeom(geom.makeCopy(), state)
            copy = parent.attachNewNode(node)
            copy.setMat(part.getMat(source))
            triangles += sum(primitive.decompose().getNumPrimitives() for primitive in geom.getPrimitives())
    for wheel in wheels.values():
        wheel.flattenStrong()
    assert root.writeBamFile(Filename.fromOsSpecific(str(OUTPUT)))
    manifest = {'source': str(SOURCE.relative_to(ROOT)), 'source_sha256': hashlib.sha256(SOURCE.read_bytes()).hexdigest(),
        'output': str(OUTPUT.relative_to(ROOT)), 'output_sha256': hashlib.sha256(OUTPUT.read_bytes()).hexdigest(),
        'triangles': triangles, 'author': 'Lionsharp Studios / Karol Miklas', 'license': 'CC-BY-4.0',
        'source_scene_manifest': 'art/vehicles/porsche-930-source.json',
        'changes': ['保留完整车身/灯组/内饰源网格', '四轮独立根', '车漆分区命名paint', '法线与材质按离线源导出']}
    (OUTPUT.parent/'porsche-930-manifest.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
    print(json.dumps(manifest, ensure_ascii=False))


if __name__ == '__main__':
    prepare()
