"""实际GLB与原生岩岸资源的数据/材质/贴图逐值对照，不开启驾驶或改变图形上下文。"""

import argparse
import hashlib
import json
import sys
import time
from pathlib import Path

import gltf
from panda3d.core import (
    Filename,
    Loader,
    LoaderOptions,
    MaterialAttrib,
    NodePath,
    RenderAttribRegistry,
    TextureAttrib,
)

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT/'tools/environment'))
from prepare_rock_runtime import OUTPUT, SOURCES


def state_signature(state):
    result = []
    for slot in range(RenderAttribRegistry.getGlobalPtr().getMaxSlots()):
        attrib = state.getAttrib(slot)
        if attrib is None:
            continue
        if isinstance(attrib, MaterialAttrib):
            value = str(attrib.getMaterial())
        elif isinstance(attrib, TextureAttrib):
            value = []
            for stage in attrib.getOnStages():
                texture = attrib.getOnTexture(stage)
                value.append((stage.getName(), stage.getMode(), stage.getSort(),
                    stage.getTexcoordName().getName(),
                    (texture.getXSize(), texture.getYSize(), texture.getZSize()),
                    texture.getFormat(), texture.getComponentType(),
                    texture.getMinfilter(), texture.getMagfilter(), texture.getAnisotropicDegree(),
                    texture.getWrapU(), texture.getWrapV(), texture.getWrapW(),
                    [hashlib.sha256(bytes(texture.getRamMipmapImage(level))).hexdigest()
                     for level in range(texture.getNumRamMipmapImages())]))
            # PBR按贴图语义绑定；同sort的stage内部顺序依赖对象地址，不能当成材质差异。
            assert len({(item[0], item[1], item[2], item[3]) for item in value}) == len(value)
            value.sort(key=lambda item: (item[0], item[1], item[2], item[3]))
        else:
            value = str(attrib)
        result.append((attrib.getType().getName(), state.getOverride(slot), value))
    return result


def signature(root):
    result = []
    for path in root.findAllMatches('**/+GeomNode'):
        for geom, state in zip(path.node().getGeoms(), path.node().getGeomStates(), strict=True):
            data = geom.getVertexData()
            result.append((path.getName(), tuple(path.getMat(root).getCell(row, col) for row in range(4) for col in range(4)), str(data.getFormat()),
                [hashlib.sha256(bytes(array.getHandle().getData())).hexdigest() for array in data.getArrays()],
                [(p.getPrimitiveType(), p.isIndexed(), p.getIndexType(),
                  tuple(p.getVertex(i) for i in range(p.getNumVertices()))) for p in geom.getPrimitives()],
                state_signature(path.getState(root).compose(state))))
    return state_signature(root.getState()), result


def check(output):
    output.mkdir(parents=True, exist_ok=False)
    rows = []
    for source_path in SOURCES:
        start = time.perf_counter()
        source = NodePath(gltf.load_model(Filename.fromOsSpecific(str(source_path))))
        original_ms = (time.perf_counter()-start)*1000
        target = OUTPUT/(source_path.stem+'.bam')
        start = time.perf_counter()
        node = Loader.getGlobalPtr().loadSync(Filename.fromOsSpecific(str(target)), LoaderOptions(LoaderOptions.LFNoCache))
        if node is None:
            raise OSError(target)
        native = NodePath(node)
        native_ms = (time.perf_counter()-start)*1000
        try:
            first, second = signature(source), signature(native)
            if first != second:
                print('ROOT', first[0], second[0], flush=True)
                for index, (a, b) in enumerate(zip(first[1], second[1], strict=True)):
                    for field, (left, right) in enumerate(zip(a, b, strict=True)):
                        if left != right:
                            print('DIFFERENCE', index, field, str(left)[:1600], str(right)[:1600], flush=True)
                            break
                    if a != b:
                        break
                raise AssertionError(source_path.name)
            assert source.getTightBounds() == native.getTightBounds()
            row = {'source': source_path.relative_to(ROOT).as_posix(),
                   'source_sha256': hashlib.sha256(source_path.read_bytes()).hexdigest(),
                   'native': target.relative_to(ROOT).as_posix(),
                   'native_sha256': hashlib.sha256(target.read_bytes()).hexdigest(),
                   'original_load_ms': original_ms, 'native_load_ms': native_ms,
                   'geometry_material_texture_equal': True}
            rows.append(row)
            print(row, flush=True)
        finally:
            source.removeNode()
            native.removeNode()
    (output/'summary.json').write_text(json.dumps({'passed': True, 'runs': rows,
        'scope': '两份真实岩岸：顶点/切线数组和索引哈希、变换、材质参数、采样设置、全部RAM mip字节及外廓相同；离场CPU加载计时，不是正常窗口响应或GPU像素Gate。'},
        ensure_ascii=False, indent=2)+'\n', encoding='utf-8')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    check(parser.parse_args().output.resolve())
