"""将GR86社区网格打包为车库和道路共用BAM，保留真实四轮分区。"""

import hashlib
import json
from pathlib import Path

import gltf
from panda3d.core import Filename, GeomNode, MaterialAttrib, NodePath, loadPrcFileData

ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT/'art/vehicles/gr86_community.glb'
OUTPUT = ROOT/'assets/game/vehicles/gr86_community.bam'
WHEELS = ('wheel-front-left', 'wheel-front-right', 'wheel-back-left', 'wheel-back-right')


def prepare():
    loadPrcFileData('', 'bam-texture-mode rawdata')
    source = NodePath(gltf.load_model(Filename.fromOsSpecific(str(SOURCE))))
    root = NodePath('gr86-community')
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
    assert triangles == 163931
    assert root.writeBamFile(Filename.fromOsSpecific(str(OUTPUT)))
    report = {'source': str(SOURCE.relative_to(ROOT)), 'source_sha256': hashlib.sha256(SOURCE.read_bytes()).hexdigest(),
        'output': str(OUTPUT.relative_to(ROOT)), 'output_sha256': hashlib.sha256(OUTPUT.read_bytes()).hexdigest(),
        'triangles': triangles, 'author': 'Mona x Supercars (Car2022)', 'license': 'CC-BY-4.0',
        'changes': ['独立四轮与paint分区', '保留完整主网格/源法线/UV/14张贴图', '使用原GR86显示外廓装配，十套物理配置保持']}
    (OUTPUT.parent/'gr86-community-manifest.json').write_text(json.dumps(report, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
    print(json.dumps(report, ensure_ascii=False))


if __name__ == '__main__':
    prepare()
