"""将已提取的俱乐部双门导出为内嵌资源的Panda显示资产。"""

import hashlib
import json
from pathlib import Path

import gltf
from panda3d.core import Filename, GeomNode, MaterialAttrib, NodePath, loadPrcFileData

ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT/'art/vehicles/club_coupe.glb'
OUTPUT = ROOT/'assets/game/vehicles/club_coupe.bam'
WHEELS = ('wheel-front-left', 'wheel-front-right', 'wheel-back-left', 'wheel-back-right')


def prepare():
    loadPrcFileData('', 'bam-texture-mode rawdata')
    source = NodePath(gltf.load_model(Filename.fromOsSpecific(str(SOURCE))))
    root = NodePath('club-coupe')
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
            triangles += sum(p.decompose().getNumPrimitives() for p in geom.getPrimitives())
    for wheel in wheels.values():
        wheel.flattenStrong()
    assert root.writeBamFile(Filename.fromOsSpecific(str(OUTPUT)))
    manifest = {'source': str(SOURCE.relative_to(ROOT)), 'source_sha256': hashlib.sha256(SOURCE.read_bytes()).hexdigest(),
        'output': str(OUTPUT.relative_to(ROOT)), 'output_sha256': hashlib.sha256(OUTPUT.read_bytes()).hexdigest(),
        'triangles': triangles, 'author': 'Mike Pan', 'license': 'CC-BY-3.0',
        'changes': ['保留GLB网格与材质', '变换烘焙，四个无缩放轮根', '主车漆分区命名paint', '原比例按实际轮位装配'],
        'source_scene_manifest': 'art/vehicles/club-coupe-source.json'}
    (OUTPUT.parent/'club-coupe-manifest.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
    print(json.dumps(manifest, ensure_ascii=False))


if __name__ == '__main__':
    prepare()
