"""从CC0实拍草图集的完整多叶草簇制作相接的低草片，不使用单茎随机散放。"""

import json
import math
import random
from pathlib import Path

import bpy
from mathutils import Vector

ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / 'art/expressway/sources/vegetation/grass_medium_01/textures'
OUT = ROOT / 'art/expressway/candidates/coastal-meadow'
# 对应作者图集中的五种完整多叶草簇，坐标按左下为原点。
REGIONS = ((.0, .0, .18, .16), (.20, .0, .45, .14), (.54, .0, .75, .11),
           (.17, .14, .37, .27), (.60, .12, .85, .26))


def build():
    OUT.mkdir(parents=True, exist_ok=True)
    bpy.ops.wm.read_factory_settings(use_empty=True)
    material = bpy.data.materials.new('photographed-low-meadow')
    material.use_nodes = True
    material.use_backface_culling = False
    material.surface_render_method = 'DITHERED'
    nodes, links = material.node_tree.nodes, material.node_tree.links
    shader = nodes.get('Principled BSDF')
    shader.inputs['Roughness'].default_value = .95
    albedo, mask = nodes.new('ShaderNodeTexImage'), nodes.new('ShaderNodeTexImage')
    albedo.image = bpy.data.images.load(str(SOURCE / 'grass_medium_01_diff_1k.jpg'))
    mask.image = bpy.data.images.load(str(SOURCE / 'grass_medium_01_alpha_1k.png'))
    mask.image.colorspace_settings.name = 'Non-Color'
    links.new(albedo.outputs['Color'], shader.inputs['Base Color'])
    links.new(mask.outputs['Color'], shader.inputs['Alpha'])
    report = []
    for level, grid in enumerate((32, 16)):
        rng = random.Random(2401)
        vertices, faces, uvs, normals = [], [], [], []
        for row in range(grid):
            for column in range(grid):
                x = (column + rng.uniform(.15, .85)) * 4 / grid - 2
                y = (row + rng.uniform(.15, .85)) * 4 / grid - 2
                height = rng.uniform(.07, .13)
                u0, v0, u1, v1 = rng.choice(REGIONS)
                width = height * (u1 - u0) / (v1 - v0) * (1 if level == 0 else 1.65)
                angle = rng.uniform(0, math.tau)
                for side in range(3):
                    heading = angle + side * math.pi / 3
                    dx, dy = math.cos(heading) * width / 2, math.sin(heading) * width / 2
                    first = len(vertices)
                    vertices.extend(((x - dx, y - dy, 0), (x + dx, y + dy, 0),
                                     (x + dx, y + dy, height), (x - dx, y - dy, height)))
                    faces.append(tuple(range(first, first + 4)))
                    uvs.extend(((u0, v0), (u1, v0), (u1, v1), (u0, v1)))
                    normal = Vector((math.sin(heading) * .12, -math.cos(heading) * .12, 1)).normalized()
                    normals.extend((normal,) * 4)
        mesh = bpy.data.meshes.new(f'coastal-meadow-lod{level}')
        mesh.from_pydata(vertices, [], faces)
        mesh.uv_layers.new()
        for loop, uv in zip(mesh.uv_layers.active.data, uvs, strict=True):
            loop.uv = uv
        mesh.normals_split_custom_set([normals[loop.vertex_index] for loop in mesh.loops])
        mesh.materials.append(material)
        obj = bpy.data.objects.new(mesh.name, mesh)
        bpy.context.scene.collection.objects.link(obj)
        report.append({'name': obj.name, 'triangles': len(faces) * 2, 'plants': grid * grid})
    bpy.ops.export_scene.gltf(filepath=str(OUT / 'coastal-meadow.glb'), export_format='GLB',
                             export_yup=True, export_normals=True, export_cameras=False,
                             export_lights=False, export_animations=False)
    bpy.ops.file.pack_all()
    bpy.ops.wm.save_as_mainfile(filepath=str(OUT / 'coastal-meadow.blend'))
    document = {'source': str(SOURCE.relative_to(ROOT)), 'license': 'CC0-1.0',
                'size_m': [4, 4], 'height_m': [.07, .13], 'regions': REGIONS,
                'models': report, 'scope': '图24低草地被候选，待实际驾驶画面验收'}
    (OUT / 'meadow.json').write_text(json.dumps(document, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print('MEADOW', json.dumps(report), flush=True)


if __name__ == '__main__':
    build()
