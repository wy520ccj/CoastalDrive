"""分开GR86后部共面装饰；源文件和GLB其他数据保持。"""

import argparse
import hashlib
import json
import struct
from pathlib import Path

import numpy as np
import zstandard
from blender_asset_tracer.blendfile import BlendFile

ROOT = Path(__file__).resolve().parents[2]


def repair_blend(source, output, evidence):
    with source.open('rb') as stream:
        original = zstandard.ZstdDecompressor().stream_reader(stream).read()
    raw = evidence/'source-uncompressed.blend'
    raw.write_bytes(original)
    edited = bytearray(original)
    changes = []
    with BlendFile(raw) as blend:
        for block in blend.find_blocks_from_code(b'OB'):
            name = block.get((b'id',b'name'))
            settings = {b'OBRear diffuser':(-2.12001,.003),b'OBRear plate':(-2.12501,.003),
                        b'OBExhaust outlet':(-2.08755,.006),b'OBExhaust outlet.001':(-2.08755,.006),
                        b'OBExhaust dark center':(-2.1306,.007),b'OBExhaust dark center.001':(-2.1306,.007)}
            if name not in settings:
                continue
            expected,translation = settings[name]
            location = block.get(b'loc')
            if abs(location[1]-expected)>1e-6:
                raise ValueError('源部件位置与待修复版本不符')
            field,offset = block.dna_type.field_from_path(blend.header.pointer_size,(b'loc',1))
            if field.dna_type.dna_type_id!=b'float':
                raise ValueError('源位置字段必须为float')
            position = block.file_offset+offset
            struct.pack_into('<f',edited,position,location[1]-translation)
            changes.append({'object':name.decode(),'offset':position,'before':location[1],
                            'after':struct.unpack_from('<f',edited,position)[0]})
    if len(changes)!=6:
        raise ValueError('源文件必须包含原后部装饰和排气部件')
    allowed = {change['offset']+index for change in changes for index in range(4)}
    if any(a!=b and index not in allowed for index,(a,b) in enumerate(zip(original,edited))):
        raise ValueError('源文件出现部件位置以外的变化')
    output.write_bytes(zstandard.ZstdCompressor(level=10).compress(edited))
    with BlendFile(output) as check:
        actual = {block.get((b'id',b'name')).decode():block.get(b'loc')[1]
                  for block in check.find_blocks_from_code(b'OB')
                  if block.get((b'id',b'name')) in settings}
    assert actual=={change['object']:change['after'] for change in changes}
    return changes


def components(document, primitive, values, binary):
    """按实际三角形和共位置顶点辨认合并前的部件，排气口不混入扩散器。"""
    accessor = document['accessors'][primitive['indices']]
    view = document['bufferViews'][accessor['bufferView']]
    dtype = {5121:'u1',5123:'<u2',5125:'<u4'}[accessor['componentType']]
    indices = np.frombuffer(binary,dtype=dtype,count=accessor['count'],
        offset=view.get('byteOffset',0)+accessor.get('byteOffset',0)).reshape(-1,3)
    parent = list(range(len(values)))

    def root(index):
        while parent[index]!=index:
            parent[index] = parent[parent[index]]
            index = parent[index]
        return index

    coordinates = {}
    for index,point in enumerate(values):
        key = tuple(point)
        if key in coordinates:
            parent[root(index)] = root(coordinates[key])
        else:
            coordinates[key] = index
    for triangle in indices:
        first = root(int(triangle[0]))
        for value in triangle[1:]:
            parent[root(int(value))] = first
    groups = {}
    for index in range(len(values)):
        groups.setdefault(root(index),[]).append(index)
    return tuple(np.array(indices,dtype=np.intp) for indices in groups.values())


def repair_glb(source, output):
    original = source.read_bytes()
    size,kind = struct.unpack_from('<II',original,12)
    if kind!=0x4e4f534a:
        raise ValueError('运行模型必须是GLB JSON/BIN格式')
    document = json.loads(original[20:20+size])
    binary_start = 20+size+8
    binary = bytearray(original[binary_start:])
    changes = []
    for node in document['nodes']:
        if node['name']=='Exhaust Steel surfaces':
            node['translation'][2] += .006
            changes.append({'material_group':node['name'],'translation_m':.006})
            continue
        if node['name'] not in ('Head Light surfaces','Satin Black Plastic surfaces'):
            continue
        if any(key in node for key in ('matrix','translation','rotation','scale')):
            raise ValueError('原后部材料组必须保留世界顶点坐标')
        for primitive in document['meshes'][node['mesh']]['primitives']:
            accessor = document['accessors'][primitive['attributes']['POSITION']]
            view = document['bufferViews'][accessor['bufferView']]
            if accessor['componentType']!=5126 or accessor['type']!='VEC3':
                raise ValueError('原模型位置必须是单精度三维向量')
            offset = view.get('byteOffset',0)+accessor.get('byteOffset',0)
            values = np.ndarray((accessor['count'],3),dtype='<f4',buffer=binary,offset=offset,
                                strides=(view.get('byteStride',12),4))
            # GLB的Y向上：制作源(x,y,z)在运行顶点中为(x,z,-y)。
            selected = ((values[:,2]>2.11)&(values[:,2]<2.14))
            if node['name']=='Head Light surfaces':
                selected &= (abs(values[:,0])<.201)&(values[:,1]>.459)&(values[:,1]<.601)
            else:
                selected = np.zeros(len(values),dtype=bool)
                centers = 0
                for indices in components(document,primitive,values,binary):
                    low,high = values[indices].min(axis=0),values[indices].max(axis=0)
                    size = high-low
                    if low[2]>2.10 and abs(float(size[0])-1.5)<1e-5:
                        selected[indices] = True
                    elif low[2]>2.12 and abs(float(size[0])-.086)<1e-5:
                        values[indices,2] += np.float32(.007)
                        centers += 1
                if centers!=2:
                    raise ValueError('运行模型必须包含两个原排气内片')
                changes.append({'material_group':node['name'],'exhaust_center_parts':centers,'translation_m':.007})
            count = int(selected.sum())
            if not count or abs(float(values[selected,2].max())-2.13251)>1e-6:
                raise ValueError('运行后部装饰与待修复版本不符')
            values[selected,2] += np.float32(.003)
            accessor['min'] = values.min(axis=0).tolist()
            accessor['max'] = values.max(axis=0).tolist()
            changes.append({'material_group':node['name'],'vertices':count,
                            'outer_surface_m':float(values[selected,2].max())})
    if len(changes)!=4:
        raise ValueError('运行模型必须包含原后部材料组和排气部件')
    encoded = json.dumps(document,separators=(',',':')).encode()
    encoded += b' '*(-len(encoded)%4)
    total = 12+8+len(encoded)+8+len(binary)
    output.write_bytes(struct.pack('<III',0x46546c67,2,total)+struct.pack('<II',len(encoded),0x4e4f534a)+encoded
                       +struct.pack('<II',len(binary),0x004e4942)+binary)
    return changes


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--evidence',type=Path,required=True)
    parser.add_argument('--originals',type=Path,help='此前证据中的original-*原始资源；用于修复方案复核')
    args = parser.parse_args()
    args.evidence.mkdir(parents=True,exist_ok=False)
    blend = ROOT/'art/vehicles/gr86_2022_premium.blend'
    glb = ROOT/'assets/game/vehicles/gr86_2022_premium.glb'
    for path in (blend,glb):
        source = args.originals/('original-'+path.name) if args.originals is not None else path
        (args.evidence/('original-'+path.name)).write_bytes(source.read_bytes())
    corrected_blend,corrected_glb = args.evidence/blend.name,args.evidence/glb.name
    report = {'blend_changes':repair_blend(args.evidence/('original-'+blend.name),corrected_blend,args.evidence),
              'glb_changes':repair_glb(args.evidence/('original-'+glb.name),corrected_glb),
              'method':'DNA loc fields and corresponding GLB vertex translation; no Blender rebuild',
              'sha256':{str(path.relative_to(ROOT)):hashlib.sha256(corrected.read_bytes()).hexdigest()
                        for path,corrected in ((blend,corrected_blend),(glb,corrected_glb))}}
    blend.write_bytes(corrected_blend.read_bytes())
    glb.write_bytes(corrected_glb.read_bytes())
    (args.evidence/'repair.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
    print(json.dumps(report,indent=2))


if __name__=='__main__':
    main()
