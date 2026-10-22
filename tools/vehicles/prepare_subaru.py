"""将有来源的WRX STI网格与贴图打包成道路/车库共用的Panda资产。"""

import hashlib
import json
from pathlib import Path

import gltf
from panda3d.core import Filename, GeomNode, MaterialAttrib, NodePath, loadPrcFileData

ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT/'art/vehicles/subaru_wrx_sti.glb'
OUTPUT = ROOT/'assets/game/vehicles/subaru_wrx_sti.bam'
WHEELS = ('wheel-front-left', 'wheel-front-right', 'wheel-back-left', 'wheel-back-right')


def prepare():
    loadPrcFileData('', 'bam-texture-mode rawdata')
    source = NodePath(gltf.load_model(Filename.fromOsSpecific(str(SOURCE))))
    root = NodePath('subaru-wrx-sti')
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
        'triangles': triangles, 'author': 'lubomircenovsky', 'license': 'CC-BY-SA-3.0',
        'source_scene_manifest': 'art/vehicles/subaru-source.json',
        'changes': ['保留源网格与贴图', '四个独立轮根', '车漆分区命名paint', '所有贴图内嵌']}
    (OUTPUT.parent/'subaru-wrx-sti-manifest.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
    print(json.dumps(manifest, ensure_ascii=False))


if __name__ == '__main__':
    prepare()
