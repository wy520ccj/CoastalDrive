"""将有许可的Car Concept适配为项目轮根和涂装分区，不重建几何。"""

import hashlib
import json
import math
from pathlib import Path

import gltf
from panda3d.core import (
    Filename,
    GeomNode,
    Mat4,
    Material,
    MaterialAttrib,
    NodePath,
    TextureAttrib,
    TransparencyAttrib,
    Vec3,
    Vec4,
    loadPrcFileData,
)

ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT/'art/vehicles/sources/car-concept/CarConcept.glb'
OUTPUT = ROOT/'assets/game/vehicles/car_concept.bam'


def prepare():
    loadPrcFileData('', 'bam-texture-mode rawdata')
    source = NodePath(gltf.load_model(Filename.fromOsSpecific(str(SOURCE))))
    result = NodePath('car-concept')
    result.setTag('authored-proportions', 'wheel-hubs')
    wheels, corrections = {}, {}
    for old, name in (('WheelFrontL', 'wheel-front-left'), ('WheelFrontR', 'wheel-front-right'),
                      ('WheelRearL', 'wheel-back-left'), ('WheelRearR', 'wheel-back-right')):
        wheels[old] = result.attachNewNode(name)
        original = source.find('**/'+old)
        axle = original.getMat(source).xformVec(Vec3(1, 0, 0))
        center = Mat4.rotateMat(180, (0, 0, 1)).xformPoint(original.getPos(source))
        angle = -math.degrees(math.atan2(axle.y, axle.x))
        corrections[old] = Mat4.translateMat(-center)*Mat4.rotateMat(angle, (0, 0, 1))*Mat4.translateMat(center)
    removed, triangles = [], 0
    for part in source.findAllMatches('**/+GeomNode'):
        ancestors = tuple(node.getName() for node in part.getAncestors())
        # 原许可不包含商标；移除车牌与方向盘标志，不以另一品牌替代。
        if 'License Plate' in ancestors or 'InteriorSteeringEmblem' in ancestors:
            removed.append(part.getName())
            continue
        wheel_name = next((old for old in wheels if old in ancestors), None)
        wheel = None if wheel_name is None else wheels[wheel_name]
        parent = result if wheel is None else wheel
        for index, geom in enumerate(part.node().getGeoms()):
            state = part.node().getGeomState(index)
            material = state.getAttrib(MaterialAttrib).getMaterial()
            textures = state.getAttrib(TextureAttrib)
            if textures is not None:
                adapted = Material(material)
                for stage in tuple(textures.getOnStages()):
                    # 共享发光贴图和胎侧色图也含商标，保留其他纹理细节。
                    if textures.getOnTexture(stage).getName() in ('gltf-embedded-3', 'gltf-embedded-11', 'gltf-embedded-12'):
                        textures = textures.removeOnStage(stage)
                        if stage.getName() == 'Emissive':
                            adapted.setEmission(Vec4(0, 0, 0, 1))
                if material.getName() == 'Tireside':
                    adapted.setBaseColor(Vec4(.02, .02, .02, 1))
                    adapted.setRoughness(.65)
                    adapted.setMetallic(0)
                state = state.setAttrib(textures)
                state = state.setAttrib(MaterialAttrib.make(adapted))
            name = 'paint' if material.getName() == 'Paint 1 Carmine' else part.getName()
            node = GeomNode(name)
            node.addGeom(geom.makeCopy(), state)
            copy = parent.attachNewNode(node)
            transform = part.getMat(source)*Mat4.rotateMat(180, (0, 0, 1))
            copy.setMat(transform if wheel_name is None else transform*corrections[wheel_name])
            if material.getName() == 'Glass':
                glass = Material(material)
                glass.setBaseColor(Vec4(.07, .12, .16, .28))
                glass.setMetallic(.05)
                glass.setRoughness(.08)
                copy.setMaterial(glass, 1)
                copy.setTransparency(TransparencyAttrib.MAlpha)
                copy.setDepthWrite(False)
            triangles += sum(p.decompose().getNumPrimitives() for p in geom.getPrimitives())
    for wheel in wheels.values():
        wheel.flattenStrong()
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    assert result.writeBamFile(Filename.fromOsSpecific(str(OUTPUT)))
    manifest = {'source': str(SOURCE.relative_to(ROOT)), 'source_sha256': hashlib.sha256(SOURCE.read_bytes()).hexdigest(),
        'output': str(OUTPUT.relative_to(ROOT)), 'output_sha256': hashlib.sha256(OUTPUT.read_bytes()).hexdigest(),
        'triangles': triangles, 'removed': removed,
        'changes': ['逐网格烘焙节点变换，保持源几何/贴图；朝向转为+Y', '统一四轮根名', '主车漆命名paint',
                    '透射玻璃适配为Panda透明PBR', '删除许可排除的车牌/方向盘标志及共享标志纹理',
                    '源文件前轮30度展示舵角归零；轮拱按实际轮位装配，物理参数不变'],
        'license': 'CC-BY-4.0', 'artist': 'Eric Chadwick', 'owner': 'Darmstadt Graphics Group GmbH', 'year': 2024}
    (OUTPUT.parent/'car-concept-manifest.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
    print(json.dumps(manifest, ensure_ascii=False))


if __name__ == '__main__':
    prepare()
