"""保留Socksthecat的BRZ Varis源曲面，替换经典车外观而不改变驾驶参数。"""

import hashlib
import json
import math
from pathlib import Path

import bmesh
import bpy
from mathutils import Matrix, Vector

ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT/'art/vehicles/sources/subaru-brz'
FIT = ROOT/'art/vehicles/brz-fit.json'
OUTPUT = ROOT/'art/vehicles/subaru_brz.glb'


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
        image.image = bpy.data.images.load(str(SOURCE/texture), check_existing=False)
        result.node_tree.links.new(image.outputs['Color'], shader.inputs['Base Color'])
    if color[3] < 1:
        result.surface_render_method = 'DITHERED'
    return result


def prepare():
    fit = json.loads(FIT.read_text(encoding='utf-8'))
    bpy.ops.wm.open_mainfile(filepath=str(SOURCE/'sx.blend'), load_ui=False, use_scripts=False)
    names = ('SX_body', 'SX_interior', 'SX_glass')
    records = [(name, bpy.data.objects[name].data.copy()) for name in names]
    with bpy.data.libraries.load(str(SOURCE/'wheel.blend'), link=False) as (original, loaded):
        loaded.objects = ['SX_wheel']
    wheel_source = loaded.objects[0].data.copy()
    scene = bpy.data.scenes.new('brz-export')
    bpy.context.window.scene = scene
    root = bpy.data.objects.new('subaru-brz', None)
    scene.collection.objects.link(root)
    # 源红图仅红通道带遮蔽；单独保存中性色图后重新加载，绕开旧内嵌红图。
    paint = bpy.data.images.load(str(SOURCE/'SX_body_red.png'), check_existing=False)
    pixels = list(paint.pixels)
    pixels[1::4], pixels[2::4] = pixels[0::4], pixels[0::4]
    paint.pixels = pixels
    paint.filepath_raw = str(ROOT/'art/vehicles/brz-body-ao.png')
    paint.file_format = 'PNG'
    paint.save()
    glass = material('Blue Grey Glass', color=(.1, .16, .22, .30), metallic=.1, roughness=.1)
    materials = {
        'SX_body': [material('Body Paint', texture='../../brz-body-ao.png', metallic=.65, roughness=.12)],
        'SX_interior': [material('Exterior lamps and trim', texture='SX_exterior.png', roughness=.34),
                        material('Cabin upholstery', texture='SX_interior.png', roughness=.65)],
        'SX_glass': [glass], 'SX_glass2': [glass],
    }
    transform = Matrix.Rotation(-math.pi/2, 4, 'Z')@Matrix.Rotation(math.pi, 4, 'X')

    def fit_scale(y):
        length_scale = (fit['wheelbase']/2/1.275 if abs(y) <= 1.275 else
            (fit['collision_half_length']-fit['wheelbase']/2)/
            ((2.291652679 if y > 0 else 2.177099943)-1.275))
        return Vector((fit['collision_half_width']/.978189647, length_scale,
                       2*fit['collision_half_height']/1.312586397))

    def fit_point(point):
        x, y, z = point
        # 前后轮拱随现有2.2m轴距移动，前后悬独立适配既有4.256m外廓。
        if abs(y) <= 1.275:
            y *= fit['wheelbase']/2/1.275
        else:
            limit = 2.291652679 if y > 0 else 2.177099943
            y = math.copysign(fit['wheelbase']/2+(abs(y)-1.275)*
                (fit['collision_half_length']-fit['wheelbase']/2)/(limit-1.275), y)
        x *= fit['collision_half_width']/.978189647
        bottom = fit['body_center_height']-fit['collision_half_height']
        height = 2*fit['collision_half_height']
        z = bottom+(z+.481446356)*height/1.312586397
        return Vector((x, y, z))

    for name, mesh in records:
        indices = [face.material_index for face in mesh.polygons]
        authored_normals = ([transform.to_3x3()@normal.vector for normal in mesh.corner_normals]
                            if name == 'SX_body' else [])
        mesh.transform(transform)
        if name == 'SX_body':
            # 轴距适配分段缩放，作者面角法线须按局部Jacobian的逆转置变换。
            for index, loop in enumerate(mesh.loops):
                normal = authored_normals[index]
                scale = fit_scale(mesh.vertices[loop.vertex_index].co.y)
                authored_normals[index] = tuple(Vector(tuple(
                    normal[a]/scale[a] for a in range(3))).normalized())
        for vertex in mesh.vertices:
            vertex.co = fit_point(vertex.co)
        if name == 'SX_body':
            corner_positions = [mesh.vertices[loop.vertex_index].co.copy() for loop in mesh.loops]
            mesh.attributes.remove(mesh.attributes['custom_normal'])
            edit = bmesh.new()
            edit.from_mesh(mesh)
            bmesh.ops.remove_doubles(edit, verts=list(edit.verts), dist=.000001)
            edit.normal_update()
            for edge in edit.edges:
                edge.smooth = len(edge.link_faces) == 2 and edge.calc_face_angle() < math.radians(40)
            edit.to_mesh(mesh)
            edit.free()
            mesh.update()
            if len(corner_positions) != len(mesh.loops) or any(
                (mesh.vertices[loop.vertex_index].co-before).length > .000002
                for loop, before in zip(mesh.loops, corner_positions, strict=True)):
                raise RuntimeError('合并重合点改变了原面角对应，不能恢复作者法线')
            mesh.normals_split_custom_set(authored_normals)
        for layer in tuple(mesh.color_attributes):
            mesh.color_attributes.remove(layer)
        mesh.materials.clear()
        for entry in materials[name]:
            mesh.materials.append(entry)
        for face, index in zip(mesh.polygons, indices, strict=True):
            face.material_index = index
        obj = bpy.data.objects.new(name, mesh)
        obj.parent = root
        scene.collection.objects.link(obj)
    tire = material('Source wheel and tire', texture='SX_wheel.png', roughness=.56)
    reflection = tire.node_tree.nodes.new('ShaderNodeTexImage')
    reflection.image = bpy.data.images.load(str(SOURCE/'SX_wheel_refl.png'), check_existing=False)
    reflection.image.colorspace_settings.name = 'Non-Color'
    tire.node_tree.links.new(reflection.outputs['Color'], tire.node_tree.nodes['Principled BSDF'].inputs['Metallic'])
    low = Vector(tuple(min(v.co[a] for v in wheel_source.vertices) for a in range(3)))
    high = Vector(tuple(max(v.co[a] for v in wheel_source.vertices) for a in range(3)))
    center = (low+high)/2
    size = high-low
    for side, axle, name in ((-1, 1, 'front-left'), (1, 1, 'front-right'),
                             (-1, -1, 'back-left'), (1, -1, 'back-right')):
        wheel = bpy.data.objects.new('wheel-'+name, None)
        wheel.parent = root
        wheel.location = (side*fit['track_width']/2, axle*fit['wheelbase']/2, fit['wheel_radius'])
        scene.collection.objects.link(wheel)
        mesh = wheel_source.copy()
        mesh.transform(Matrix.Translation(-center))
        matrix = Matrix.Diagonal((-side*fit['wheel_width']/size.x,
            2*fit['wheel_radius']/size.y, 2*fit['wheel_radius']/size.z, 1))
        mesh.transform(matrix)
        if matrix.determinant() < 0:
            mesh.flip_normals()
        for layer in tuple(mesh.color_attributes):
            mesh.color_attributes.remove(layer)
        mesh.materials.clear()
        mesh.materials.append(tire)
        obj = bpy.data.objects.new('source-wheel-'+name, mesh)
        obj.parent = wheel
        scene.collection.objects.link(obj)
    bpy.ops.export_scene.gltf(filepath=str(OUTPUT), export_format='GLB', export_yup=True,
        export_apply=True, export_extras=True, export_cameras=False, export_lights=False, use_active_scene=True)
    for original in tuple(bpy.data.scenes):
        if original != scene:
            bpy.data.scenes.remove(original)
    for obj in tuple(bpy.data.objects):
        if obj.name not in scene.objects:
            bpy.data.objects.remove(obj, do_unlink=True)
    bpy.ops.outliner.orphans_purge(do_recursive=True)
    bpy.ops.file.pack_all()
    bpy.ops.wm.save_as_mainfile(filepath=str(ROOT/'art/vehicles/subaru_brz.blend'))
    report = {'author': 'Socksthecat', 'source_import': 'CryHam / Stunt Rally', 'license': 'CC-BY-4.0',
        'source': 'https://github.com/stuntrally/blendfiles/tree/master/cars/SX',
        'source_sha256': hashlib.sha256((SOURCE/'sx.blend').read_bytes()).hexdigest(),
        'output_sha256': hashlib.sha256(OUTPUT.read_bytes()).hexdigest(),
        'fit_sha256': hashlib.sha256(FIT.read_bytes()).hexdigest(),
        'geometry': [*names, 'SX_wheel'], 'changes': ['只提取主车与完整源轮网格', '按已有经典车外廓/轮位适配',
            '中性遮蔽和PBR材质', '保留内外饰两套原材质分区', '按局部逆转置保留作者车漆面角法线', '四轮独立由Snapshot驱动'],
        'physics': 'Unchanged game-tuned config; not Subaru OEM calibration'}
    (ROOT/'art/vehicles/brz-source.json').write_text(json.dumps(report, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
    print(json.dumps(report, ensure_ascii=False))


if __name__ == '__main__':
    prepare()
