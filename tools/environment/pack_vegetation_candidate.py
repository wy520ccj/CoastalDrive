"""打包源植物的距离档与共享贴图；运行时复用原生LOD和既有分段生命周期。"""

import hashlib
import json
from pathlib import Path

import gltf
from panda3d.core import (
    AlphaTestAttrib,
    DepthWriteAttrib,
    Filename,
    LODNode,
    NodePath,
    Texture,
    TextureAttrib,
    TransparencyAttrib,
    loadPrcFileData,
)

ROOT = Path(__file__).resolve().parents[2]


def main():
    loadPrcFileData('', 'bam-texture-mode rawdata')
    path = ROOT/'art/expressway/candidates/play-repair-vegetation.glb'
    source = NodePath(gltf.load_model(Filename.fromOsSpecific(str(path))))
    root = NodePath('photographed-vegetation')
    for part in source.findAllMatches('**/+GeomNode'):
        for index, state in enumerate(part.node().getGeomStates()):
            textures = state.getAttrib(TextureAttrib)
            for stage in tuple(textures.getOnStages()):
                if stage.getName() != 'Base Color':
                    textures = textures.removeOnStage(stage)
            state = state.setAttrib(textures)
            state = state.removeAttrib(TransparencyAttrib.getClassType())
            state = state.setAttrib(AlphaTestAttrib.make(AlphaTestAttrib.MGreaterEqual, .45))
            state = state.setAttrib(DepthWriteAttrib.make(DepthWriteAttrib.MOn))
            part.node().setGeomState(index, state)
    specifications = (
        ('broadleaf-a', ('tree-lod0', 'tree-lod1', 'tree-lod2'), ((35, 0), (120, 35), (560, 120)), 2.7),
        ('broadleaf-b', ('tree-coastal-lod0', 'tree-coastal-lod1', 'tree-coastal-lod2'), ((35, 0), (120, 35), (560, 120)), 2.7),
        ('fine-shrubs', ('shrub-lod0', 'shrub-far-lod0'), ((18, 0), (560, 18)), .425),
        ('source-grass', ('grass-lod0', 'grass-far-lod0'), ((55, 0), (140, 55)), .225),
    )
    for key, names, ranges, center in specifications:
        lod = LODNode(key)
        lod.setCenter((0, 0, center))
        node = root.attachNewNode(lod)
        for name, switch in zip(names, ranges, strict=True):
            mesh = source.find('**/'+name)
            if mesh.isEmpty():
                raise ValueError(f'缺少植物距离档：{name}')
            copy = mesh.copyTo(node)
            copy.clearModelNodes()
            copy.flattenStrong()
            if switch[1] > 0:
                copy.setTag('distant-plant', '1')
                copy.setAttrib(AlphaTestAttrib.make(AlphaTestAttrib.MGreaterEqual, .12), 1)
            lod.addSwitch(*switch)
    for texture in root.findAllTextures():
        texture.setMinfilter(Texture.FTLinearMipmapLinear)
        texture.setAnisotropicDegree(4)
    out = ROOT/'art/expressway/candidates/play-repair-vegetation.bam'
    assert root.writeBamFile(Filename.fromOsSpecific(str(out)))
    report = {'source': str(path.relative_to(ROOT)), 'source_sha256': hashlib.sha256(path.read_bytes()).hexdigest(),
        'output_sha256': hashlib.sha256(out.read_bytes()).hexdigest(), 'textures': root.findAllTextures().getNumTextures(),
        'author': 'Poly Haven: Rob Tuytel / Rico Cilliers / James Ray Cock / Jenelle van Heerden', 'license': 'CC0-1.0',
        'note': 'Tree Small 02 / Island Tree 01 / Wild Rooibos Bush / Grass Bermuda 01；仅枝干面内简化，完整叶簇按距离抽稀并补偿覆盖率；原碰撞保持。'}
    out.with_suffix('.manifest.json').write_text(json.dumps(report, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
    print(json.dumps(report, ensure_ascii=False))


if __name__ == '__main__':
    main()
