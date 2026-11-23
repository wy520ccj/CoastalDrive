"""把CC0源树的细枝和叶子烘成空间枝簇图集，保留原树冠与独立树干。"""

import json
import math
from pathlib import Path

import bpy
import numpy as np
from mathutils import Matrix, Vector

ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / 'art/expressway/sources/vegetation/island_tree_01'
OUT = ROOT / 'art/expressway/candidates/coastal-canopy'
HEIGHT = 8.5
TILE = 256


def emit_material(name, color, alpha=None):
    material = bpy.data.materials.new(name)
    material.use_nodes = True
    material.surface_render_method = 'DITHERED'
    nodes = material.node_tree.nodes
    nodes.clear()
    texture = nodes.new('ShaderNodeTexImage')
    texture.image = bpy.data.images.load(str(SOURCE / 'textures' / color), check_existing=True)
    emission = nodes.new('ShaderNodeEmission')
    transparent = nodes.new('ShaderNodeBsdfTransparent')
    mix = nodes.new('ShaderNodeMixShader')
    output = nodes.new('ShaderNodeOutputMaterial')
    links = material.node_tree.links
    links.new(texture.outputs['Color'], emission.inputs['Color'])
    links.new(transparent.outputs[0], mix.inputs[1])
    links.new(emission.outputs[0], mix.inputs[2])
    if alpha:
        mask = nodes.new('ShaderNodeTexImage')
        mask.image = bpy.data.images.load(str(SOURCE / 'textures' / alpha), check_existing=True)
        mask.image.colorspace_settings.name = 'Non-Color'
        links.new(mask.outputs['Color'], mix.inputs[0])
    else:
        mix.inputs[0].default_value = 1
    links.new(mix.outputs[0], output.inputs[0])
    return material


def subset(name, indices, positions, faces, uvs, material_ids, materials):
    selected = faces[indices]
    vertices, inverse = np.unique(selected.ravel(), return_inverse=True)
    mesh = bpy.data.meshes.new(name)
    mesh.vertices.add(len(vertices))
    mesh.vertices.foreach_set('co', positions[vertices].ravel())
    mesh.loops.add(len(inverse))
    mesh.loops.foreach_set('vertex_index', inverse)
    mesh.polygons.add(len(indices))
    mesh.polygons.foreach_set('loop_start', np.arange(len(indices), dtype=np.int32) * 3)
    mesh.polygons.foreach_set('loop_total', np.full(len(indices), 3, dtype=np.int32))
    mesh.polygons.foreach_set('material_index', material_ids[indices])
    mesh.uv_layers.new().data.foreach_set('uv', uvs[indices].ravel())
    for material in materials:
        mesh.materials.append(material)
    mesh.update()
    return mesh


def build():
    OUT.mkdir(parents=True, exist_ok=True)
    bpy.ops.wm.read_factory_settings(use_empty=True)
    bpy.ops.import_scene.gltf(filepath=str(SOURCE / 'island_tree_01_1k.gltf'))
    source = next(obj for obj in bpy.context.scene.objects if obj.type == 'MESH')
    mesh = source.data
    mesh.transform(source.matrix_world)
    source.matrix_world = Matrix.Identity(4)
    low_z = min(v.co.z for v in mesh.vertices)
    scale = HEIGHT / (max(v.co.z for v in mesh.vertices) - low_z)
    mesh.transform(Matrix.Scale(scale, 4) @ Matrix.Translation((0, 0, -low_z)))
    positions = np.empty(len(mesh.vertices) * 3, dtype=np.float32)
    mesh.vertices.foreach_get('co', positions)
    positions = positions.reshape(-1, 3)
    faces = np.empty(len(mesh.loops), dtype=np.int32)
    mesh.loops.foreach_get('vertex_index', faces)
    faces = faces.reshape(-1, 3)
    assert len(faces) == len(mesh.polygons), '源glTF应为三角面'
    uvs = np.empty(len(mesh.loops) * 2, dtype=np.float32)
    mesh.uv_layers.active.data.foreach_get('uv', uvs)
    uvs = uvs.reshape(-1, 3, 2)
    ids = np.empty(len(mesh.polygons), dtype=np.int32)
    mesh.polygons.foreach_get('material_index', ids)
    originals = list(mesh.materials)
    leaf_id = next(i for i, mat in enumerate(originals) if mat.name == 'island_tree_01_leaves')
    twig_id = next(i for i, mat in enumerate(originals) if mat.name == 'island_tree_01_branches')
    trunk_ids = np.where((ids != leaf_id) & (ids != twig_id))[0]
    trunk_mesh = subset('source-trunk', trunk_ids, positions, faces, uvs, ids, originals)
    foliage_ids = np.where((ids == leaf_id) | (ids == twig_id))[0]
    centers = positions[faces[foliage_ids]].mean(axis=1)
    low = centers.min(axis=0)
    extent = centers.max(axis=0) - low
    cells = np.minimum(3, ((centers - low) / extent * 4).astype(np.int32))
    keys = cells[:, 0] + 4 * cells[:, 1] + 16 * cells[:, 2]
    bake_materials = list(originals)
    bake_materials[leaf_id] = emit_material('bake-source-leaves', 'island_tree_01_leaves_diff_1k.jpg',
                                           'island_tree_01_leaves_alpha_1k.png')
    bake_materials[twig_id] = emit_material('bake-source-twigs', 'island_tree_01_branches_diff_1k.jpg')
    clusters = []
    for key in sorted(np.unique(keys)):
        indices = foliage_ids[keys == key]
        if len(indices) < 16:
            continue
        cluster_mesh = subset(f'branch-cluster-{key}', indices, positions, faces, uvs, ids, bake_materials)
        coords = np.array([tuple(v.co) for v in cluster_mesh.vertices])
        a, b = coords.min(axis=0), coords.max(axis=0)
        center = Vector((a + b) / 2)
        cluster_mesh.transform(Matrix.Translation(-center))
        obj = bpy.data.objects.new(cluster_mesh.name, cluster_mesh)
        bpy.context.scene.collection.objects.link(obj)
        clusters.append({'object': obj, 'center': center, 'size': b - a, 'faces': len(indices)})
    bpy.data.objects.remove(source, do_unlink=True)
    print('BRANCH CLUSTERS', len(clusters), 'TRUNK TRIANGLES', len(trunk_ids), flush=True)
    scene = bpy.context.scene
    scene.render.engine = 'BLENDER_EEVEE'
    scene.eevee.taa_render_samples = 32
    scene.render.film_transparent = True
    scene.render.image_settings.file_format = 'PNG'
    scene.render.image_settings.color_mode = 'RGBA'
    scene.view_settings.view_transform = 'Standard'
    scene.view_settings.look = 'None'
    scene.view_settings.exposure = 0
    scene.view_settings.gamma = 1
    columns = math.ceil(math.sqrt(len(clusters)))
    scene.render.resolution_x = scene.render.resolution_y = columns * TILE
    scene.render.resolution_percentage = 100
    camera_data = bpy.data.cameras.new('atlas-camera')
    camera = bpy.data.objects.new('atlas-camera', camera_data)
    scene.collection.objects.link(camera)
    camera.location = (0, 0, 100)
    camera_data.type = 'ORTHO'
    camera_data.ortho_scale = columns
    scene.camera = camera
    views = (
        ('front', Matrix(((1, 0, 0), (0, 0, 1), (0, -1, 0))), (0, 2)),
        ('side', Matrix(((0, 1, 0), (0, 0, 1), (1, 0, 0))), (1, 2)),
        ('top', Matrix.Identity(3), (0, 1)),
    )
    records = []
    for name, rotation, axes in views:
        for index, cluster in enumerate(clusters):
            frame = max(cluster['size'][axis] for axis in axes) * 1.08
            cluster[name + '-frame'] = frame
            x, y = index % columns, index // columns
            location = (x + .5 - columns / 2, y + .5 - columns / 2, 0)
            cluster['object'].matrix_world = Matrix.Translation(location) @ rotation.to_4x4() @ Matrix.Scale(1 / frame, 4)
        scene.render.filepath = str(OUT / (name + '.png'))
        bpy.ops.render.render(write_still=True)
        print('ATLAS', name, scene.render.filepath, flush=True)
    for cluster in clusters:
        bpy.data.objects.remove(cluster['object'], do_unlink=True)
    bpy.data.objects.remove(camera, do_unlink=True)
    # 三个正交叶卡保留同一空间枝簇，不用整树面片冒充近景树。
    materials = []
    for name, _, _ in views:
        material = bpy.data.materials.new('canopy-' + name)
        material.use_nodes = True
        material.use_backface_culling = False
        material.surface_render_method = 'DITHERED'
        nodes = material.node_tree.nodes
        shader = nodes.get('Principled BSDF')
        shader.inputs['Roughness'].default_value = .88
        image = nodes.new('ShaderNodeTexImage')
        image.image = bpy.data.images.load(str(OUT / (name + '.png')), check_existing=True)
        material.node_tree.links.new(image.outputs['Color'], shader.inputs['Base Color'])
        material.node_tree.links.new(image.outputs['Alpha'], shader.inputs['Alpha'])
        materials.append(material)
    vertices, polygons, uv_values, normal_values, slots = [], [], [], [], []
    for index, cluster in enumerate(clusters):
        u, v = index % columns / columns, index // columns / columns
        for view, (name, rotation, _) in enumerate(views):
            frame = cluster[name + '-frame']
            inverse = rotation.inverted()
            start = len(vertices)
            for x, y in ((-.5, -.5), (.5, -.5), (.5, .5), (-.5, .5)):
                p = cluster['center'] + inverse @ Vector((x * frame, y * frame, 0))
                vertices.append(p)
                normal_values.append((p - Vector((0, 0, HEIGHT * .58))).normalized())
            polygons.append(tuple(range(start, start + 4)))
            uv_values.extend(((u, v), (u + 1 / columns, v),
                              (u + 1 / columns, v + 1 / columns), (u, v + 1 / columns)))
            slots.append(view)
        records.append({'center': list(cluster['center']), 'source_triangles': cluster['faces']})
    cards = bpy.data.meshes.new('authored-canopy-cards')
    cards.from_pydata(vertices, [], polygons)
    cards.uv_layers.new().data.foreach_set('uv', np.array(uv_values, dtype=np.float32).ravel())
    cards.polygons.foreach_set('material_index', slots)
    for material in materials:
        cards.materials.append(material)
    cards.normals_split_custom_set([normal_values[loop.vertex_index] for loop in cards.loops])
    for level, ratio in enumerate((1., .3, .08)):
        obj = bpy.data.objects.new(f'coastal-tree-lod{level}', trunk_mesh.copy())
        scene.collection.objects.link(obj)
        bpy.context.view_layer.objects.active = obj
        if ratio != 1:
            modifier = obj.modifiers.new('仅树干距离档', 'DECIMATE')
            modifier.ratio = ratio
            bpy.ops.object.modifier_apply(modifier=modifier.name)
        leaves = bpy.data.objects.new(f'coastal-leaves-lod{level}', cards.copy())
        scene.collection.objects.link(leaves)
        leaves.parent = obj
    bpy.ops.export_scene.gltf(filepath=str(OUT / 'coastal-tree.glb'), export_format='GLB',
                             export_yup=True, export_normals=True, export_cameras=False,
                             export_lights=False, export_animations=False)
    bpy.ops.outliner.orphans_purge(do_recursive=True)
    bpy.ops.file.pack_all()
    bpy.ops.wm.save_as_mainfile(filepath=str(OUT / 'coastal-tree.blend'))
    report = {'source': str(SOURCE.relative_to(ROOT)), 'license': 'CC0-1.0', 'height_m': HEIGHT,
              'source_triangles': len(faces), 'trunk_triangles': len(trunk_ids),
              'canopy_triangles': len(polygons) * 2, 'atlas_size': columns * TILE,
              'clusters': records, 'scope': '完整源树的空间枝簇烘焙；尚未作为运行资产验收'}
    (OUT / 'bake.json').write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print('BAKE FINISHED', len(polygons) * 2, 'CANOPY TRIANGLES', flush=True)


if __name__ == '__main__':
    build()
