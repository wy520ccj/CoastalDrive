"""提取lubomircenovsky的WRX STI源网格，保留车身/内饰和源轮胎轮毂。"""

import hashlib
import json
import math
from pathlib import Path

import bpy
from mathutils import Matrix, Vector

ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT/'art/vehicles/sources/subaru-wrx-sti'
OUTPUT = ROOT/'art/vehicles/subaru_wrx_sti.glb'


def material(name, *, texture=None, color=(1, 1, 1, 1), metallic=0., roughness=.4):
    result = bpy.data.materials.new(name)
    result.diffuse_color = color
    result.use_nodes = True
    shader = result.node_tree.nodes['Principled BSDF']
    shader.inputs['Base Color'].default_value = color
    shader.inputs['Metallic'].default_value = metallic
    shader.inputs['Roughness'].default_value = roughness
    shader.inputs['Alpha'].default_value = color[3]
    if texture is not None:
        image = result.node_tree.nodes.new('ShaderNodeTexImage')
        # 不复用旧blend中同名的内嵌图，避免导出仍取到修改前的红色贴图。
        image.image = bpy.data.images.load(str(SOURCE/texture), check_existing=False)
        result.node_tree.links.new(image.outputs['Color'], shader.inputs['Base Color'])
    if color[3] < 1:
        result.surface_render_method = 'DITHERED'
    return result


def prepare():
    bpy.ops.wm.open_mainfile(filepath=str(SOURCE/'wrx_08.blend'), load_ui=False, use_scripts=False)
    deps = bpy.context.evaluated_depsgraph_get()
    records = [(name, bpy.data.objects[name].data.copy()) for name in ('S8_body', 'S8_glass', 'S8_interior')]
    rim = bpy.data.meshes.new_from_object(bpy.data.objects['subaru_wheel.F.L.001'].evaluated_get(deps), depsgraph=deps)
    tire = bpy.data.meshes.new_from_object(bpy.data.objects['subaru_wheel_tire.007'].evaluated_get(deps), depsgraph=deps)
    scene = bpy.data.scenes.new('subaru-export')
    bpy.context.window.scene = scene
    root = bpy.data.objects.new('subaru-wrx-sti', None)
    scene.collection.objects.link(root)
    root['authored-proportions'] = 'wheel-hubs'
    root['license'] = 'CC-BY-SA-3.0'
    # 源图红通道含车身遮蔽细节，提取为中性色，避免蓝色车漆被红底相乘成黑色。
    paint = bpy.data.images.load(str(SOURCE/'S8_body_red.png'), check_existing=True)
    pixels = list(paint.pixels)
    pixels[1::4] = pixels[0::4]
    pixels[2::4] = pixels[0::4]
    paint.pixels = pixels
    paint.filepath_raw = str(ROOT/'art/vehicles/subaru-body-ao.png')
    paint.file_format = 'PNG'
    paint.save()
    paint.filepath = paint.filepath_raw
    materials = {
        'S8_body': [material('Body Paint', texture='../../subaru-body-ao.png', metallic=.65, roughness=.12)],
        'S8_glass': [material('Glass', color=(.09, .14, .18, .30), metallic=.15, roughness=.1)],
        'S8_interior': [material('Cabin and exterior details', texture='S8_interior.png', roughness=.45),
                        material('Rear lamps', texture='S8_rear_lights.png', roughness=.22)],
    }
    transform = Matrix.Rotation(-math.pi/2, 4, 'Z')@Matrix.Rotation(math.pi, 4, 'X')
    for name, mesh in records:
        for layer in tuple(mesh.color_attributes):
            mesh.color_attributes.remove(layer)
        mesh.transform(transform)
        mesh.materials.clear()
        for entry in materials[name]:
            mesh.materials.append(entry)
        obj = bpy.data.objects.new(name, mesh)
        obj.parent = root
        scene.collection.objects.link(obj)
    gold = material('Gold alloy', color=(.52, .30, .075, 1), metallic=.85, roughness=.24)
    rubber = material('Source tire', color=(.014, .017, .021, 1), roughness=.72)
    # 源轮毂已完整建模，轮胎也是源细分网格；不以新建圆柱替代。
    low = Vector(tuple(min(vertex.co[a] for vertex in tire.vertices) for a in range(3)))
    high = Vector(tuple(max(vertex.co[a] for vertex in tire.vertices) for a in range(3)))
    center = (low+high)/2
    for side, axle, name in ((-1, 1.267, 'front-left'), (1, 1.267, 'front-right'),
                             (-1, -1.336, 'back-left'), (1, -1.336, 'back-right')):
        wheel = bpy.data.objects.new('wheel-'+name, None)
        wheel.parent = root
        wheel.location = (side*.77, axle, -.57)
        scene.collection.objects.link(wheel)
        for source, mat, part in ((rim, gold, 'alloy'), (tire, rubber, 'tire')):
            mesh = source.copy()
            mesh.transform(Matrix.Translation(-center))
            # 源轮毂面朝+X；左侧镜像后修正面向。
            mesh.transform(Matrix.Diagonal((side, 1, 1, 1)))
            if side < 0:
                mesh.flip_normals()
            mesh.materials.clear()
            mesh.materials.append(mat)
            obj = bpy.data.objects.new(part+' '+name, mesh)
            obj.parent = wheel
            scene.collection.objects.link(obj)
    bpy.ops.export_scene.gltf(filepath=str(OUTPUT), export_format='GLB', export_yup=True,
        export_apply=True, export_extras=True, export_cameras=False, export_lights=False, use_active_scene=True)
    # 可编辑衍生文件只保留本车导出场景；原始工程另行原样归档。
    for original in tuple(bpy.data.scenes):
        if original != scene:
            bpy.data.scenes.remove(original)
    for obj in tuple(bpy.data.objects):
        if obj.name not in scene.objects:
            bpy.data.objects.remove(obj, do_unlink=True)
    bpy.ops.outliner.orphans_purge(do_recursive=True)
    bpy.ops.file.pack_all()
    bpy.ops.wm.save_as_mainfile(filepath=str(ROOT/'art/vehicles/subaru_wrx_sti.blend'))
    report = {'author': 'lubomircenovsky', 'license': 'CC-BY-SA-3.0',
        'source': 'https://github.com/stuntrally/blendfiles/blob/master/cars/S8/wrx_08.blend',
        'source_sha256': hashlib.sha256((SOURCE/'wrx_08.blend').read_bytes()).hexdigest(),
        'output_sha256': hashlib.sha256(OUTPUT.read_bytes()).hexdigest(),
        'source_geometry': ['S8_body', 'S8_glass', 'S8_interior', 'subaru_wheel.F.L.001', 'subaru_wheel_tire.007'],
        'changes': ['仅提取单车主网格和完整源车轮', '轴向转换', '原纹理接入PBR', '红通道遮蔽转中性色', '独立四轮和可变车漆'],
        'adaptation_license': 'CC-BY-SA-3.0; source and editable derivative included'}
    (ROOT/'art/vehicles/subaru-source.json').write_text(json.dumps(report, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
    print(json.dumps(report, ensure_ascii=False))


if __name__ == '__main__':
    prepare()
