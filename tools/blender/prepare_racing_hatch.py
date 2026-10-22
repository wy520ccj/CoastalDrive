"""保留ANDREO12的i20网格与贴图，适配已有H1轮位和显示边界。"""

import hashlib
import json
import math
from pathlib import Path

import bpy
from mathutils import Matrix, Vector

ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT/'art/vehicles/sources/hyundai-i20'
FIT = ROOT/'art/vehicles/hatch-fit.json'
OUTPUT = ROOT/'art/vehicles/racing_hatch.glb'


def material(name, texture=None, *, metallic=0., roughness=.45, color=(1, 1, 1, 1)):
    result = bpy.data.materials.new(name)
    result.use_nodes = True
    result.diffuse_color = color
    shader = result.node_tree.nodes['Principled BSDF']
    shader.inputs['Base Color'].default_value = color
    shader.inputs['Metallic'].default_value = metallic
    shader.inputs['Roughness'].default_value = roughness
    shader.inputs['Alpha'].default_value = color[3]
    if texture is not None:
        image = result.node_tree.nodes.new('ShaderNodeTexImage')
        image.image = bpy.data.images.load(str(SOURCE/texture), check_existing=True)
        result.node_tree.links.new(image.outputs['Color'], shader.inputs['Base Color'])
    if color[3] < 1:
        result.surface_render_method = 'DITHERED'
    if name == 'Wheel':
        image = result.node_tree.nodes.new('ShaderNodeTexImage')
        image.image = bpy.data.images.load(str(SOURCE/'HI_wheel_refl.png'), check_existing=True)
        image.image.colorspace_settings.name = 'Non-Color'
        result.node_tree.links.new(image.outputs['Color'], shader.inputs['Metallic'])
    return result


def prepare():
    fit = json.loads(FIT.read_text(encoding='utf-8'))
    bpy.ops.wm.open_mainfile(filepath=str(SOURCE/'hi.blend'), load_ui=False, use_scripts=False)
    meshes = [(obj.name, obj.data.copy(), obj.matrix_world.copy()) for obj in bpy.context.scene.objects if obj.type == 'MESH']
    with bpy.data.libraries.load(str(SOURCE/'hi-wheel.blend'), link=False) as (original, loaded):
        loaded.objects = [name for name in original.objects if name in ('HI_brake', 'HI_disk', 'HI_wheel')]
    wheel_parts = [(obj.name, obj.data.copy(), obj.matrix_world.copy()) for obj in loaded.objects]
    scene = bpy.data.scenes.new('i20-export')
    bpy.context.window.scene = scene
    root = bpy.data.objects.new('racing-hatch', None)
    root['authored-proportions'] = 'wheel-hubs'
    scene.collection.objects.link(root)
    materials = {
        'HI_body': material('Body Paint', 'HI_body_red.png', metallic=.45, roughness=.23),
        'HI_interior': material('Interior and trim', 'HI_interior.png', roughness=.40),
        'HI_glass': material('Glass', metallic=.1, roughness=.12, color=(.12, .18, .23, .32)),
        'HI_wheel': material('Wheel', 'HI_wheel.png', roughness=.42),
        'HI_disk': material('Brake disc', 'HI_wheel.png', metallic=.8, roughness=.3),
        'HI_brake': material('Brake caliper', color=(.24, .035, .025, 1), roughness=.35),
    }
    transform = Matrix.Rotation(-math.pi/2, 4, 'Z')@Matrix.Rotation(math.pi, 4, 'X')
    target_half = fit['wheelbase']/2
    source_half, source_track, source_radius = 1.275, 1.76, .327752
    target_radius = fit['wheel_radius']
    # 仅适配已有显示尺寸：轮拱附近保留轮径，收短前后悬与车顶上方空间。
    # 不改动任何运行时物理配置，所有新增曲面均来自原车网格。
    def fit_point(point):
        x, y, z = point
        side, end = math.copysign(1, x), math.copysign(1, y)
        hub_x = fit['track_width']/2
        if abs(x) <= source_track/2:
            x *= fit['track_width']/source_track
        else:
            x = side*(hub_x+(abs(x)-source_track/2)*
                      (fit['collision_half_width']+.05-hub_x)/(1.123-source_track/2))
        if abs(y) <= source_half:
            y *= target_half/source_half
        else:
            limit = 2.105533 if y > 0 else 2.020038
            y = end*(target_half+(abs(y)-source_half)*(fit['collision_half_length']-target_half)/(limit-source_half))
        # 源拉力车轮拱顶部约z=.16；保留4cm静态间隙，避免沿用源赛用高离地姿态。
        source_arch_top = .16
        target_arch_top = target_radius*2+.04
        if z <= source_arch_top:
            sill = fit['body_center_height']-fit['collision_half_height']+.002
            z = target_arch_top+(z-source_arch_top)*(target_arch_top-sill)/(source_arch_top+.458105)
        else:
            roof = fit['body_center_height']+fit['collision_half_height']-.002
            z = target_arch_top+(z-source_arch_top)*(roof-target_arch_top)/(.922639-source_arch_top)
        return Vector((x, y, z))

    for name, mesh, matrix in meshes:
        for layer in tuple(mesh.color_attributes):
            mesh.color_attributes.remove(layer)
        mesh.transform(transform@matrix)
        for vertex in mesh.vertices:
            vertex.co = fit_point(vertex.co)
        mesh.materials.clear()
        mesh.materials.append(materials[name])
        obj = bpy.data.objects.new(name, mesh)
        scene.collection.objects.link(obj)
        obj.parent = root
    for side, axle, title in ((-1, 1, 'front-left'), (1, 1, 'front-right'),
                              (-1, -1, 'back-left'), (1, -1, 'back-right')):
        wheel = bpy.data.objects.new('wheel-'+title, None)
        scene.collection.objects.link(wheel)
        wheel.parent = root
        wheel.location = (side*fit['track_width']/2, axle*target_half, target_radius)
        for name, original, matrix in wheel_parts:
            mesh = original.copy()
            for layer in tuple(mesh.color_attributes):
                mesh.color_attributes.remove(layer)
            mesh.transform(matrix)
            # 源独立车轮沿X轴，左右镜像保持外侧朝外，轮根无额外缩放。
            wheel_matrix = Matrix.Diagonal((-side*fit['wheel_width']/.2553573,
                                           target_radius/source_radius, target_radius/source_radius, 1))
            mesh.transform(wheel_matrix)
            if wheel_matrix.determinant() < 0:
                mesh.flip_normals()
            mesh.materials.clear()
            mesh.materials.append(materials[name])
            obj = bpy.data.objects.new(name+' '+title, mesh)
            scene.collection.objects.link(obj)
            obj.parent = wheel
    bpy.ops.export_scene.gltf(filepath=str(OUTPUT), export_format='GLB', export_yup=True,
        export_apply=True, export_extras=True, export_cameras=False, export_lights=False, use_active_scene=True)
    bpy.ops.wm.save_as_mainfile(filepath=str(ROOT/'art/vehicles/racing_hatch.blend'))
    manifest = {'author': 'ANDREO12', 'source_import_fixes': 'CryHam / Stunt Rally', 'license': 'CC-BY-4.0',
        'source': 'https://github.com/stuntrally/blendfiles/tree/master/cars/HI',
        'textures': 'https://github.com/stuntrally/stuntrally3/tree/main/data/cars/HI/textures',
        'fit': str(FIT.relative_to(ROOT)), 'fit_sha256': hashlib.sha256(FIT.read_bytes()).hexdigest(),
        'sha256': hashlib.sha256(OUTPUT.read_bytes()).hexdigest(),
        'changes': ['原车身/内饰/玻璃/轮胎/制动网格保留', '源轴向转换', '按现有H1轮位和显示边界适配',
                    '原AO及内饰/车轮贴图接入PBR', '未使用带赞助商字样的拉力涂装图'],
        'physics': 'Unchanged CoastalDrive coastal-hatch setup; not Hyundai OEM calibration'}
    (ROOT/'art/vehicles/racing-hatch-source.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
    print(json.dumps(manifest, ensure_ascii=False))


if __name__ == '__main__':
    prepare()
