"""从CC0源树、灌木、草簇导出距离档；不制作替代原植物的球冠或三角草。"""

import json
import math
import random
from pathlib import Path

import bmesh
import bpy
from mathutils import Matrix, Vector

ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT/'art/expressway/sources/vegetation'
OUT = ROOT/'art/expressway/candidates/play-repair-vegetation.glb'


def tree_canopy(mesh, fraction, leaf_scale):
    """按完整叶簇抽稀远景；不把叶边塌成细刺，放大留下的叶簇补偿覆盖率。"""
    bm = bmesh.new()
    bm.from_mesh(mesh)
    leaves = {i for i, material in enumerate(mesh.materials) if '_leaves' in material.name}
    for face in bm.faces:
        face.tag = False
    rng = random.Random(421)
    removed = []
    for face in bm.faces:
        if face.material_index not in leaves or face.tag:
            continue
        face.tag = True
        stack, group = [face], []
        while stack:
            current = stack.pop()
            group.append(current)
            for edge in current.edges:
                for adjacent in edge.link_faces:
                    if not adjacent.tag and adjacent.material_index in leaves:
                        adjacent.tag = True
                        stack.append(adjacent)
        if rng.random() > fraction:
            removed.extend(group)
        elif leaf_scale != 1:
            vertices = {vertex for member in group for vertex in member.verts}
            center = sum((v.co for v in vertices), Vector())/len(vertices)
            for vertex in vertices:
                vertex.co = center+(vertex.co-center)*leaf_scale
    bmesh.ops.delete(bm, geom=removed, context='FACES')
    bm.to_mesh(mesh)
    bm.free()
    mesh.transform(Matrix.Translation((0,0,-min(v.co.z for v in mesh.vertices))))


def build():
    OUT.parent.mkdir(parents=True, exist_ok=True)
    bpy.ops.wm.read_factory_settings(use_empty=True)
    records = []
    for path, selected, label in (
        ('../tree-small-02/tree_small_02_1k.gltf', 'tree_small_02_LOD0', 'tree'),
        ('island_tree_01/island_tree_01_1k.gltf', 'island_tree_01_LOD0', 'tree-coastal'),
        ('wild_rooibos_bush/wild_rooibos_bush_1k.gltf', 'wild_rooibos_bush_b', 'shrub'),
        ('wild_rooibos_bush/wild_rooibos_bush_1k.gltf', 'wild_rooibos_bush_e', 'shrub-far'),
        ('../grass-bermuda-01/grass_bermuda_01_1k.gltf', 'grass_bermuda_01_medium_a', 'grass'),
        ('../grass-bermuda-01/grass_bermuda_01_1k.gltf', 'grass_bermuda_01_small_a', 'grass-far'),
    ):
        before = set(bpy.context.scene.objects)
        bpy.ops.import_scene.gltf(filepath=str(SOURCE/path))
        bpy.context.view_layer.update()
        imported = set(bpy.context.scene.objects)-before
        source = next(obj for obj in imported if obj.type == 'MESH' and obj.name.startswith(selected))
        mesh = source.data.copy()
        mesh.transform(source.matrix_world)
        # Panda只使用一个顶点色通道，保留源首通道，避免多色层映成同名列。
        for attribute in tuple(mesh.color_attributes)[1:]:
            mesh.color_attributes.remove(attribute)
        # 主站glTF只带RGB底色；接回作者单独发布的遮罩，保留真实叶片轮廓。
        for material in mesh.materials:
            shader = material.node_tree.nodes.get('Principled BSDF')
            mask = ('../tree-small-02/textures/tree_small_02_leaves_alpha_1k.png' if material.name.startswith('tree_small_02_leaves') else
                    'island_tree_01/textures/island_tree_01_leaves_alpha_1k.png' if material.name.startswith('island_tree_01_leaves') else
                    'wild_rooibos_bush/textures/wild_rooibos_bush_alpha_1k.png' if material.name.startswith(('wild_rooibos_bush_twigs','wild_rooibos_bush_leaves')) else
                    '../grass-bermuda-01/textures/grass_bermuda_01_alpha_1k.png' if label.startswith('grass') else None)
            if mask is not None:
                image = material.node_tree.nodes.new('ShaderNodeTexImage')
                image.image = bpy.data.images.load(str(SOURCE/mask), check_existing=True)
                image.image.colorspace_settings.name = 'Non-Color'
                material.node_tree.links.new(image.outputs['Color'], shader.inputs['Alpha'])
                material.surface_render_method = 'DITHERED'
        records.append((label, mesh))
        for obj in imported:
            bpy.data.objects.remove(obj, do_unlink=True)
    report = []
    for label, original in records:
        specifications = ((label, None, 5.4 if label.startswith('tree') else .85 if label.startswith('shrub') else .45),)
        for name, cutoff, height in specifications:
            base = original.copy()
            low = Vector(tuple(min(v.co[a] for v in base.vertices) for a in range(3)))
            high = Vector(tuple(max(v.co[a] for v in base.vertices) for a in range(3)))
            # 源树的地面轴心不跟随偏冠的包围盒偏移；草/灌木按其源实际外廓居中。
            center = Vector((0., 0., low.z)) if label.startswith('tree') else Vector(((low.x+high.x)/2, (low.y+high.y)/2, low.z))
            base.transform(Matrix.Scale(height/(high.z-low.z), 4)@Matrix.Translation(-center))
            if label.startswith('tree'):
                # 源glTF的法线缝重复顶点先焊合；保留材质/UV边界后溶解内部曲面。
                bm = bmesh.new()
                bm.from_mesh(base)
                bmesh.ops.remove_doubles(bm, verts=list(bm.verts), dist=.00001)
                bm.to_mesh(base)
                bm.free()
                # 闭合薄叶没有开放边界，不能以大角度整体溶解，否则会消失。
                bm = bmesh.new()
                bm.from_mesh(base)
                leaf_materials = {i for i,m in enumerate(base.materials) if '_leaves' in m.name}
                edges = [e for e in bm.edges if all(f.material_index not in leaf_materials for f in e.link_faces)]
                verts = [v for v in bm.verts if all(f.material_index not in leaf_materials for f in v.link_faces)]
                bmesh.ops.dissolve_limit(bm, angle_limit=math.radians(89.4),
                    use_dissolve_boundaries=False, verts=verts, edges=edges, delimit={'MATERIAL','UV'})
                bm.to_mesh(base)
                bm.free()
            ratios = ((.15,.06,.02) if label == 'tree-coastal' else
                      (.06,.025,.008) if label == 'tree' else (1.,))
            for level, ratio in enumerate(ratios):
                obj = bpy.data.objects.new(f'{name}-lod{level}', base.copy())
                bpy.context.scene.collection.objects.link(obj)
                bpy.context.view_layer.objects.active = obj
                if label.startswith('tree'):
                    tree_canopy(obj.data, ratio, (1.8, 2.4, 3.4)[level])
                obj.data.calc_loop_triangles()
                report.append({'name': obj.name, 'triangles': len(obj.data.loop_triangles),
                    'source': label, 'leaf_fraction': ratio if label.startswith('tree') else None,
                    'height': height, 'cutoff_z': cutoff})
    images = {}
    for image in tuple(bpy.data.images):
        path = bpy.path.abspath(image.filepath)
        if path in images:
            image.user_remap(images[path])
        else:
            images[path] = image
    bpy.ops.export_scene.gltf(filepath=str(OUT), export_format='GLB', export_yup=True,
        export_apply=True, export_extras=True, export_cameras=False, export_lights=False,
        export_animations=False)
    bpy.ops.outliner.orphans_purge(do_recursive=True)
    bpy.ops.file.pack_all()
    bpy.ops.wm.save_as_mainfile(filepath=str(OUT.with_suffix('.blend')))
    OUT.with_suffix('.json').write_text(json.dumps(report, indent=2)+'\n', encoding='utf-8')
    print(json.dumps(report))


if __name__ == '__main__':
    build()
