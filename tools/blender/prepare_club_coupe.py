"""从Mike Pan源场景提取一辆车，保留源网格并转换旧Cycles材质。"""

import hashlib
import json
import math
from pathlib import Path

import bpy
from mathutils import Matrix, Vector

ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT/'art/vehicles/sources/bmw27/BMW27.blend'
OUTPUT = ROOT/'art/vehicles/club_coupe.glb'
WHEELS = ('wheel-front-right', 'wheel-front-left', 'wheel-back-left', 'wheel-back-right')


def pbr_material(source):
    name = source.name
    paint = name == 'CarShellNew'
    rubber = name == 'TireRubber'
    glass = name in ('Glass', 'HeadlightGlass', 'HeadlightMatte')
    metal = name in ('Chrome', 'ChromeMatte', 'HeadlightChrome', 'Brake')
    color = ((.62, .13, .025, 1) if paint else (.018, .018, .018, 1) if rubber else
             (.08, .12, .16, .26) if glass else (.48, .50, .52, 1) if metal else (.025, .028, .032, 1))
    material = bpy.data.materials.new('Body Paint' if paint else name+' PBR')
    material.diffuse_color = color
    material.use_nodes = True
    shader = material.node_tree.nodes['Principled BSDF']
    shader.inputs['Base Color'].default_value = color
    shader.inputs['Metallic'].default_value = .45 if paint else .88 if metal else 0.
    shader.inputs['Roughness'].default_value = .24 if paint else .8 if rubber else .10 if glass else .26 if metal else .5
    shader.inputs['Coat Weight'].default_value = 1. if paint else 0.
    shader.inputs['Alpha'].default_value = color[3]
    if glass:
        material.surface_render_method = 'DITHERED'
    if name in ('HeadLightAngelEye', 'HeadLightGlass', 'Emit'):
        shader.inputs['Emission Color'].default_value = (.72, .80, 1., 1)
        shader.inputs['Emission Strength'].default_value = .5
    if name == 'Tailight':
        shader.inputs['Base Color'].default_value = (.28, .006, .003, 1)
        shader.inputs['Emission Color'].default_value = (.25, .003, .001, 1)
        shader.inputs['Emission Strength'].default_value = .5
    return material


def prepare():
    bpy.ops.wm.open_mainfile(filepath=str(SOURCE), load_ui=False, use_scripts=False)
    source_scene = bpy.context.scene
    shell = bpy.data.objects['carShell']
    members = {shell, *shell.children_recursive}
    for bone in bpy.data.objects['carController'].pose.bones:
        bone.matrix_basis.identity()
    bpy.context.view_layer.update()
    deps = bpy.context.evaluated_depsgraph_get()
    records, removed = [], set()
    source_materials = {}
    transform = Matrix.Rotation(-math.pi/2, 4, 'Z')@shell.matrix_world.inverted()
    excluded = {'RoundelFront', 'RoundelBack', 'TireRoundel', 'plate', 'MStreak'}
    for instance in deps.object_instances:
        obj = instance.object.original
        parent = instance.parent.original if instance.parent else None
        selected = (not instance.is_instance and obj in members or
                    instance.is_instance and parent in members and parent.name.startswith(('Tire', 'Brake')))
        if obj.type != 'MESH' or not selected:
            continue
        if obj.name in excluded:
            removed.add(obj.name)
            continue
        mesh = bpy.data.meshes.new_from_object(instance.object, depsgraph=deps)
        for index, material in enumerate(mesh.materials):
            if material.name not in source_materials:
                source_materials[material.name] = pbr_material(material)
            mesh.materials[index] = source_materials[material.name]
        wheel = None
        if parent is not None and parent.name.startswith(('Tire', 'Brake')):
            wheel = WHEELS[int(parent.name[-1])-1]
        matrix = transform@instance.matrix_world
        if wheel is not None:
            hub = transform@parent.matrix_world.translation
            axle = (transform@parent.matrix_world).to_3x3()@Vector((0, 1, 0))
            angle = math.atan2(axle.y, axle.x)
            if abs(angle) > math.pi/2:
                angle -= math.copysign(math.pi, angle)
            matrix = Matrix.Translation(hub)@Matrix.Rotation(-angle, 4, 'Z')@Matrix.Translation(-hub)@matrix
            if parent.name == 'Tire1':
                # 源前右轮是负缩放实例；归零展示角后将轮毂的外侧恢复朝外。
                matrix = Matrix.Translation(hub)@Matrix.Diagonal((-1, 1, 1, 1))@Matrix.Translation(-hub)@matrix
        records.append((obj.name, mesh, matrix, wheel))
    scene = bpy.data.scenes.new('club-coupe-export')
    bpy.context.window.scene = scene
    root = bpy.data.objects.new('club-coupe', None)
    root['authored-proportions'] = 'wheel-hubs'
    scene.collection.objects.link(root)
    wheel_roots = {}
    for name in WHEELS:
        node = bpy.data.objects.new(name, None)
        node.parent = root
        scene.collection.objects.link(node)
        wheel_roots[name] = node
    for name, mesh, matrix, wheel in records:
        obj = bpy.data.objects.new(name+' source', mesh)
        scene.collection.objects.link(obj)
        obj.parent = root if wheel is None else wheel_roots[wheel]
        # 源场景变换烘焙到网格，运行时的轮枢轴保持无缩放。
        mesh.transform(matrix)
        if matrix.determinant() < 0:
            mesh.flip_normals()
        mesh.update()
    source_scene.world = None
    bpy.ops.export_scene.gltf(filepath=str(OUTPUT), export_format='GLB', export_yup=True,
        export_apply=True, export_extras=True, export_cameras=False, export_lights=False, use_active_scene=True)
    bpy.ops.wm.save_as_mainfile(filepath=str(ROOT/'art/vehicles/club_coupe.blend'))
    manifest = {'source': str(SOURCE.relative_to(ROOT)), 'source_sha256': hashlib.sha256(SOURCE.read_bytes()).hexdigest(),
        'output': str(OUTPUT.relative_to(ROOT)), 'sha256': hashlib.sha256(OUTPUT.read_bytes()).hexdigest(),
        'author': 'Mike Pan', 'license': 'CC-BY-3.0', 'extracted_meshes': len(records), 'removed_marks': sorted(removed),
        'changes': ['提取单车与四轮实例', '源网格保留，变换烘焙', '旧Cycles节点转换PBR', '移除标志和车牌',
                    '负缩放绕序修正，前右轮外侧归一'],
        'physics': 'CoastalDrive generic club coupe; no source/OEM physical data inferred'}
    (OUTPUT.parent/'club-coupe-source.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
    print(json.dumps(manifest, ensure_ascii=False))


if __name__ == '__main__':
    prepare()
