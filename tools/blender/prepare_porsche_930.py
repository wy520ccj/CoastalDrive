"""保留Lionsharp的930源曲面和面角法线，归正展示前轮并独立导出。"""

import hashlib
import json
import math
from pathlib import Path

import bpy
from mathutils import Matrix, Vector

ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT/'art/vehicles/sources/porsche-930/porsche-930-original.glb'
OUTPUT = ROOT/'art/vehicles/porsche_930.glb'
WHEELS = {'Circle.051_37': 'front-left', 'Circle.037_2': 'front-right',
          'Circle.050_51': 'back-left', 'Circle.038_1': 'back-right'}


def prepare():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    bpy.ops.import_scene.gltf(filepath=str(SOURCE))
    bpy.context.view_layer.update()
    objects = [obj for obj in bpy.context.scene.objects if obj.type == 'MESH']
    hubs = {}
    corrections = {}
    for source_name, wheel_name in WHEELS.items():
        tire = next(obj for obj in objects if obj.parent.name == source_name and obj.data.materials[0].name == '930_tire')
        points = [tire.matrix_world@v.co for v in tire.data.vertices]
        low = Vector(tuple(min(p[a] for p in points) for a in range(3)))
        high = Vector(tuple(max(p[a] for p in points) for a in range(3)))
        hubs[wheel_name] = (low+high)/2
        axle = tire.parent.matrix_world.to_3x3()@Vector((1, 0, 0))
        angle = math.atan2(axle.y, axle.x)
        corrections[source_name] = Matrix.Rotation(-angle, 4, 'Z')
    mid = (hubs['front-left']+hubs['back-left'])/2
    mid.x = 0.
    scale = 2.343/abs(hubs['front-left'].y-hubs['back-left'].y)
    rotation = Matrix.Rotation(math.pi, 4, 'Z')
    transform = Matrix.Scale(scale, 4)@rotation@Matrix.Translation(-Vector((0, mid.y, 0)))
    scene = bpy.data.scenes.new('porsche-930-export')
    bpy.context.window.scene = scene
    root = bpy.data.objects.new('porsche-930', None)
    root['authored-proportions'] = 'wheel-hubs'
    scene.collection.objects.link(root)
    wheels = {}
    for name, hub in hubs.items():
        wheel = bpy.data.objects.new('wheel-'+name, None)
        wheel.parent = root
        wheel.location = transform@hub
        scene.collection.objects.link(wheel)
        wheels[name] = wheel
    paint = bpy.data.materials.new('Body Paint')
    paint.use_nodes = True
    shader = paint.node_tree.nodes['Principled BSDF']
    shader.inputs['Base Color'].default_value = (1, 1, 1, 1)
    shader.inputs['Metallic'].default_value = .65
    shader.inputs['Roughness'].default_value = .12
    # 当前运行着色器不支持glTF体透射，前灯保护罩改为薄层透明材质。
    lens = bpy.data.materials['930_lights_refraction']
    lens_shader = lens.node_tree.nodes['Principled BSDF']
    lens_shader.inputs['Base Color'].default_value = (.8, .85, .9, 1)
    lens_shader.inputs['Alpha'].default_value = .16
    lens_shader.inputs['Metallic'].default_value = .2
    lens_shader.inputs['Roughness'].default_value = .10
    lens_shader.inputs['Transmission Weight'].default_value = 0.
    lens.surface_render_method = 'DITHERED'
    triangles = 0
    excluded = []
    for source in objects:
        material = source.data.materials[0]
        # 独立覆漆由游戏既有透明面层取代；源阴影平面和天线不参与车身取景。
        if material.name in ('coat', 'material_0', '930_wunderbaum') or source.parent.name == 'Cylinder.006_20':
            excluded.append(source.name)
            continue
        mesh = source.data.copy()
        matrix = transform@source.matrix_world
        wheel_name = WHEELS.get(source.parent.name)
        if source.parent.name == 'Circle.048_52':
            wheel_name = 'front-left'
        if wheel_name:
            correction = corrections['Circle.051_37' if source.parent.name == 'Circle.048_52' else source.parent.name]
            hub = hubs[wheel_name]
            matrix = Matrix.Translation(-wheels[wheel_name].location)@transform@Matrix.Translation(hub)@correction@Matrix.Translation(-hub)@source.matrix_world
        normal_matrix = matrix.to_3x3().inverted().transposed()
        normals = [(normal_matrix@normal.vector).normalized() for normal in mesh.corner_normals]
        mesh.transform(matrix)
        mesh.update()
        mesh.normals_split_custom_set(normals)
        if material.name == 'paint':
            mesh.materials[0] = paint
        obj = bpy.data.objects.new(source.name, mesh)
        obj.parent = wheels[wheel_name] if wheel_name else root
        scene.collection.objects.link(obj)
        mesh.calc_loop_triangles()
        triangles += len(mesh.loop_triangles)
    bpy.ops.export_scene.gltf(filepath=str(OUTPUT), export_format='GLB', export_yup=True,
        export_apply=True, export_extras=True, export_cameras=False, export_lights=False,
        export_animations=False, use_active_scene=True)
    for old in tuple(bpy.data.scenes):
        if old != scene:
            bpy.data.scenes.remove(old)
    for obj in tuple(bpy.data.objects):
        if obj.name not in scene.objects:
            bpy.data.objects.remove(obj, do_unlink=True)
    bpy.ops.outliner.orphans_purge(do_recursive=True)
    bpy.ops.file.pack_all()
    bpy.ops.wm.save_as_mainfile(filepath=str(OUTPUT.with_suffix('.blend')))
    report = {'author': 'Lionsharp Studios / Karol Miklas', 'license': 'CC-BY-4.0',
        'source_sha256': hashlib.sha256(SOURCE.read_bytes()).hexdigest(),
        'output_sha256': hashlib.sha256(OUTPUT.read_bytes()).hexdigest(), 'triangles': triangles,
        'uniform_scale': scale, 'excluded_objects': excluded,
        'changes': ['保留源曲面、贴图、UV与面角法线', '归正源展示舵角，四轮独立',
                    '统一米制/车头朝向', '排除独立覆漆/源阴影平面/天线/挂件', '车漆接入游戏涂装',
                    '前灯罩体透射转换为运行着色器支持的薄层透明']}
    (ROOT/'art/vehicles/porsche-930-source.json').write_text(json.dumps(report, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
    print(json.dumps(report, ensure_ascii=False))


if __name__ == '__main__':
    prepare()
