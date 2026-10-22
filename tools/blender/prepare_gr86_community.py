"""从公开CC-BY衍生数据读取GR86实车网格，不执行下载的JavaScript。"""

import base64
import gzip
import hashlib
import json
import re
import struct
from pathlib import Path

import bpy

ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT/'art/vehicles/sources/gr86-community'
OUTPUT = ROOT/'art/vehicles/gr86_community.glb'


def linear(value):
    return value/12.92 if value <= .04045 else ((value+.055)/1.055)**2.4


def prepare():
    text = (SOURCE/'gr86-runtime.js').read_text(encoding='utf-8')
    encoded = re.search(r'ManufacturerModels\.registerCompressed\(("[A-Za-z0-9+/=]+")\);\s*$', text)
    assert encoded is not None
    data = json.loads(gzip.decompress(base64.b64decode(json.loads(encoded[1]))))
    assert data['triangles'] == 166669 and data['source']['license'] == 'CC BY 4.0'
    bpy.ops.wm.read_factory_settings(use_empty=True)
    scene = bpy.context.scene
    root = bpy.data.objects.new('gr86-community', None)
    scene.collection.objects.link(root)
    root['license'] = 'CC-BY-4.0'
    images = []
    for index, uri in enumerate(data['textures']):
        mime, encoded_image = uri.split(',', 1)
        assert mime == 'data:image/png;base64'
        path = SOURCE/f'texture-{index:02}.png'
        path.write_bytes(base64.b64decode(encoded_image))
        images.append(bpy.data.images.load(str(path)))
    wheels = {}
    for wheel in data['wheelCenters']:
        name = 'wheel-'+('front' if wheel['axle'] == 'front' else 'back')+('-left' if wheel['side'] < 0 else '-right')
        obj = bpy.data.objects.new(name, None)
        obj.parent = root
        scene.collection.objects.link(obj)
        wheels[wheel['name']] = obj
    triangles = 0
    duplicate_faces = 0
    for index, part in enumerate(data['primitives']):
        raw = base64.b64decode(part['vertices'])
        rows = list(struct.iter_unpack('<8f', raw))
        positions = [(v[1], v[0], v[2]) for v in rows]
        normals = [(v[4], v[3], v[5]) for v in rows]
        raw_indices = base64.b64decode(part['indices'])
        indices = [v[0] for v in struct.iter_unpack('<H' if part['indexType'] == 2 else '<I', raw_indices)]
        # 交换纵横轴是镜像变换，面序同步反转，UV保持源glTF约定。
        faces = []
        seen = set()
        for i in range(0, len(indices), 3):
            face = (indices[i], indices[i+2], indices[i+1])
            key = tuple(sorted(face))
            if key in seen:
                duplicate_faces += 1
                continue
            seen.add(key)
            faces.append(face)
        mesh = bpy.data.meshes.new(part['materialName']+f'-{index}')
        mesh.from_pydata(positions, [], faces)
        uv = mesh.uv_layers.new(name='UVMap')
        for loop in mesh.loops:
            row = rows[loop.vertex_index]
            uv.data[loop.index].uv = (row[6], 1-row[7])
        for face in mesh.polygons:
            face.use_smooth = True
        mesh.normals_split_custom_set_from_vertices(normals)
        material = bpy.data.materials.new('Body Paint' if part['paint'] else part['materialName'])
        material.use_nodes = True
        shader = material.node_tree.nodes['Principled BSDF']
        shader.inputs['Base Color'].default_value = (1, 1, 1, 1) if part['paint'] else (*map(linear, part['color']), part['alpha'])
        shader.inputs['Metallic'].default_value = .65 if part['paint'] else .7 if part['material'] == 3 else 0
        shader.inputs['Roughness'].default_value = .12 if part['paint'] else .25 if part['material'] in (1, 3, 4) else .6
        if 'textureIndex' in part:
            image = material.node_tree.nodes.new('ShaderNodeTexImage')
            image.image = images[part['textureIndex']]
            image.extension = 'REPEAT'
            tint = material.node_tree.nodes.new('ShaderNodeMixRGB')
            tint.blend_type = 'MULTIPLY'
            tint.inputs[0].default_value = 1.
            tint.inputs[2].default_value = (*map(linear, part['color']), 1.)
            material.node_tree.links.new(image.outputs['Color'], tint.inputs[1])
            material.node_tree.links.new(tint.outputs['Color'], shader.inputs['Base Color'])
            if not part['textureOpaque']:
                material.node_tree.links.new(image.outputs['Alpha'], shader.inputs['Alpha'])
                material.surface_render_method = 'DITHERED'
        if part['material'] == 1:
            shader.inputs['Alpha'].default_value = part['alpha']
            shader.inputs['Roughness'].default_value = .08
            if 'textureIndex' not in part:
                shader.inputs['Base Color'].default_value = (.045, .065, .08, part['alpha'])
            material.surface_render_method = 'DITHERED'
        mesh.materials.append(material)
        obj = bpy.data.objects.new('gr86-'+str(index), mesh)
        obj.parent = wheels[part['wheel']['name']] if 'wheel' in part else root
        scene.collection.objects.link(obj)
        triangles += len(faces)
    assert triangles == 163931 and duplicate_faces == 2738
    bpy.ops.export_scene.gltf(filepath=str(OUTPUT), export_format='GLB', export_yup=True,
        export_extras=True, export_animations=False, export_cameras=False, export_lights=False)
    bpy.ops.file.pack_all()
    bpy.ops.wm.save_as_mainfile(filepath=str(ROOT/'art/vehicles/gr86_community.blend'))
    report = {'author': data['source']['author'], 'license': data['source']['license'],
        'source': data['source']['url'], 'triangles': triangles, 'textures': len(images),
        'source_triangles': data['triangles'], 'removed_identical_index_faces': duplicate_faces,
        'source_sha256': hashlib.sha256((SOURCE/'gr86-runtime.js').read_bytes()).hexdigest(),
        'output_sha256': hashlib.sha256(OUTPUT.read_bytes()).hexdigest(),
        'changes': ['读取公开衍生网格，不执行外部脚本', '坐标转换与面序修正', '移除2738个相同顶点索引的重合三角面', '保留源UV/法线/贴图与四轮',
                    '车漆PBR分区/玻璃透明', '道路与车库共用资产；物理配置不变']}
    (ROOT/'art/vehicles/gr86-community-source.json').write_text(json.dumps(report, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
    print(json.dumps(report, ensure_ascii=False))


if __name__ == '__main__':
    prepare()
