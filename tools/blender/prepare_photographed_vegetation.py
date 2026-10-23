"""从CC0源树、灌木、草簇导出距离档；不制作替代原植物的球冠或三角草。"""

import json
from pathlib import Path

import bpy
from mathutils import Matrix, Vector

ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT/'art/expressway/sources/vegetation'
OUT = ROOT/'art/expressway/photographed_vegetation.glb'


def build():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    records = []
    for path, selected, label in (
        ('island_tree_01/island_tree_01_1k.gltf', 'island_tree_01_LOD0', 'tree'),
        ('wild_rooibos_bush/wild_rooibos_bush_1k.gltf', 'wild_rooibos_bush_b', 'shrub'),
        ('wild_rooibos_bush/wild_rooibos_bush_1k.gltf', 'wild_rooibos_bush_e', 'shrub-far'),
        ('grass_medium_01/grass_medium_01_1k.gltf', 'grass_medium_01_small_a_LOD0', 'grass'),
        ('grass_medium_01/grass_medium_01_1k.gltf', 'grass_medium_01_tiny_c_LOD0', 'grass-far'),
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
            mask = ('island_tree_01/textures/island_tree_01_leaves_alpha_1k.png' if material.name.startswith('island_tree_01_leaves') else
                    'wild_rooibos_bush/textures/wild_rooibos_bush_alpha_1k.png' if material.name.startswith(('wild_rooibos_bush_twigs','wild_rooibos_bush_leaves')) else
                    'grass_medium_01/textures/grass_medium_01_alpha_1k.png' if label.startswith('grass') else None)
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
        specifications = ((label, None, 5.4 if label == 'tree' else .85 if label.startswith('shrub') else .45),)
        for name, cutoff, height in specifications:
            base = original.copy()
            low = Vector(tuple(min(v.co[a] for v in base.vertices) for a in range(3)))
            high = Vector(tuple(max(v.co[a] for v in base.vertices) for a in range(3)))
            # 源树的地面轴心不跟随偏冠的包围盒偏移；草/灌木按其源实际外廓居中。
            center = Vector((0., 0., low.z)) if label == 'tree' else Vector(((low.x+high.x)/2, (low.y+high.y)/2, low.z))
            base.transform(Matrix.Scale(height/(high.z-low.z), 4)@Matrix.Translation(-center))
            ratios = (.055,) if label == 'tree' else (1.,)
            for level, ratio in enumerate(ratios):
                obj = bpy.data.objects.new(f'{name}-lod{level}', base.copy())
                bpy.context.scene.collection.objects.link(obj)
                bpy.context.view_layer.objects.active = obj
                if ratio < 1:
                    modifier = obj.modifiers.new('源网格距离简化', 'DECIMATE')
                    modifier.ratio = ratio
                    modifier.use_collapse_triangulate = True
                    bpy.ops.object.modifier_apply(modifier=modifier.name)
                obj.data.calc_loop_triangles()
                report.append({'name': obj.name, 'triangles': len(obj.data.loop_triangles),
                    'source': label, 'ratio': ratio, 'height': height, 'cutoff_z': cutoff})
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
    (ROOT/'art/expressway/vegetation-extraction.json').write_text(json.dumps(report, indent=2)+'\n', encoding='utf-8')
    print(json.dumps(report))


if __name__ == '__main__':
    build()
