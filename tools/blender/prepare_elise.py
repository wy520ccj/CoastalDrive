"""提取Stéphane Agullo的Elise源曲面，四轮独立，保留已有敞篷车硬件。"""

import hashlib
import json
from pathlib import Path

import bmesh
import bpy
from mathutils import Vector

ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT/'art/vehicles/sources/lotus-elise'
OUTPUT = ROOT/'art/vehicles/lotus_elise.glb'
WHEEL_LAYERS = {2: 'front-left', 16: 'front-right', 17: 'back-left', 18: 'back-right'}


def material(name, color, metallic=0., roughness=.4):
    result = bpy.data.materials.new(name)
    result.diffuse_color = color
    result.use_nodes = True
    shader = result.node_tree.nodes['Principled BSDF']
    shader.inputs['Base Color'].default_value = color
    shader.inputs['Metallic'].default_value = metallic
    shader.inputs['Roughness'].default_value = roughness
    shader.inputs['Alpha'].default_value = color[3]
    if color[3] < 1:
        result.surface_render_method = 'DITHERED'
    return result


def prepare():
    fit = json.loads((ROOT/'art/vehicles/elise-fit.json').read_text(encoding='utf-8'))
    bpy.ops.wm.read_factory_settings(use_empty=True)
    bpy.ops.import_scene.gltf(filepath=str(SOURCE/'lotus-elise-original.glb'))
    bpy.context.scene.frame_set(0)
    bpy.context.view_layer.update()
    records = [(obj.name, obj.data.copy(), obj.matrix_world.copy()) for obj in bpy.context.scene.objects
               if obj.type == 'MESH' and obj.name.startswith('LOTUS-def.3:') and
               not any(token in obj.name for token in (':Layer3_', ':Layer10_CAR.black', ':Layer11_'))]
    # 源轮胎的外廓用于定位轮心，不从表现资产改写物理尺寸。
    hubs = {}
    for layer in WHEEL_LAYERS:
        name, mesh, transform = next(record for record in records if f':Layer{layer}_CAR.black' in record[0])
        points = [transform@vertex.co for vertex in mesh.vertices]
        low = Vector(tuple(min(p[a] for p in points) for a in range(3)))
        high = Vector(tuple(max(p[a] for p in points) for a in range(3)))
        hubs[layer] = ((low+high)/2, (high.z-low.z)/2)
    mid_y = (hubs[2][0].y+hubs[17][0].y)/2
    scale_y = fit['wheelbase']/(hubs[2][0].y-hubs[17][0].y)
    scale_z = fit['wheel_radius']/hubs[17][1]
    scene = bpy.data.scenes.new('elise-export')
    bpy.context.window.scene = scene
    root = bpy.data.objects.new('lotus-elise', None)
    scene.collection.objects.link(root)
    root['authored-proportions'] = 'wheel-hubs'
    root['license'] = 'CC-BY-4.0'
    paint = material('Body Paint', (1., 1., 1., 1.), metallic=.65, roughness=.12)
    rubber = material('Elise source tires and black trim', (.018, .021, .025, 1.), roughness=.65)
    alloy = material('Elise source alloy', (.35, .37, .39, 1.), metallic=.85, roughness=.24)
    interior = material('Elise cabin upholstery', (.065, .07, .075, 1.), roughness=.65)
    glass = material('Elise clear glass', (.12, .19, .23, .23), metallic=.1, roughness=.10)
    mirror = material('Elise mirrors', (.65, .68, .70, 1.), metallic=1., roughness=.05)
    plate = material('Elise blank plates', (.68, .70, .72, 1.), roughness=.4)
    logo = material('Elise neutral hub caps', (.22, .24, .26, 1.), metallic=.7, roughness=.25)
    red = material('Elise red tail lamps', (.45, .015, .01, 1.), metallic=.12, roughness=.18)
    amber = material('Elise amber lamps', (.7, .23, .015, 1.), metallic=.12, roughness=.18)
    lens = material('Elise headlamp lenses', (.60, .65, .70, 1.), metallic=.65, roughness=.12)
    materials = {'carros': paint, 'black': rubber, 'chrome': alloy, 'gris': interior,
        'verre': glass, 'mirroir': mirror, 'plaque': plate, 'logo': logo,
        'feu': red, 'feu-2': amber, 'lamp-arr-bas': red, 'lamp-arr-orange': amber,
        'lamp-arr-rouge': red, 'lamp-avant-bas': lens, 'lamp-avant-haut': lens, 'lamp-avant-milieu': lens}
    wheels = {}
    for layer, name in WHEEL_LAYERS.items():
        wheel = bpy.data.objects.new('wheel-'+name, None)
        wheel.parent = root
        side = -1 if 'left' in name else 1
        front = 'front' in name
        wheel.location = (side*fit['track_width']/2, (1 if front else -1)*fit['wheelbase']/2, fit['wheel_radius'])
        scene.collection.objects.link(wheel)
        wheels[layer] = wheel
    triangles = 0
    for name, mesh, transform in records:
        layer = int(name.split(':Layer')[1].split('_')[0])
        source_material = name.split('_CAR.')[1].removesuffix('_0')
        # 厂标/方向盘徽章不进入运行资产，原件仍完整保存。
        if source_material == 'ecusson' or (source_material == 'logo' and layer not in wheels):
            continue
        mesh.transform(transform)
        for vertex in mesh.vertices:
            point = vertex.co
            if layer in wheels:
                center, radius = hubs[layer]
                point -= center
                point.x *= fit['wheel_width']/.418224
                point.y *= fit['wheel_radius']/radius
                point.z *= fit['wheel_radius']/radius
            else:
                x = abs(point.x)*fit['collision_half_width']/1.3237114
                # 后视镜保留源曲面；只压缩镜臂在原车显示宽度内。
                if x > fit['collision_half_width']:
                    x = fit['collision_half_width']+(x-fit['collision_half_width'])*.45
                point.x = (-1 if point.x < 0 else 1)*x
                point.y = (point.y-mid_y)*scale_y
                point.z = fit['wheel_radius']+(point.z-hubs[17][0].z)*scale_z+.008
        if 'custom_normal' in mesh.attributes:
            mesh.attributes.remove(mesh.attributes['custom_normal'])
        edit = bmesh.new()
        edit.from_mesh(mesh)
        bmesh.ops.remove_doubles(edit, verts=list(edit.verts), dist=.000001)
        bmesh.ops.recalc_face_normals(edit, faces=list(edit.faces))
        edit.to_mesh(mesh)
        edit.free()
        mesh.materials.clear()
        mesh.materials.append(materials[source_material])
        for face in mesh.polygons:
            face.use_smooth = True
        for attr in tuple(mesh.color_attributes):
            mesh.color_attributes.remove(attr)
        obj = bpy.data.objects.new(name.replace('LOTUS-def.3:', ''), mesh)
        obj.parent = wheels.get(layer, root)
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
    bpy.ops.wm.save_as_mainfile(filepath=str(ROOT/'art/vehicles/lotus_elise.blend'))
    report = {'author': 'Stéphane Agullo', 'license': 'CC-BY-4.0', 'source_model':
        'https://sketchfab.com/3d-models/lotus-elise-75e9045ac1af4cdbb69318108c81edfd',
        'source_sha256': hashlib.sha256((SOURCE/'lotus-elise-original.glb').read_bytes()).hexdigest(),
        'output_sha256': hashlib.sha256(OUTPUT.read_bytes()).hexdigest(), 'triangles': triangles,
        'changes': ['提取完整车身/内饰/四轮', '移除场景/人物/动画/软顶与天线', '保留源曲面并适配已有硬件外廓',
                    '重算变形后的法线', 'PBR材质转换/可变车漆', '徽章移除/车牌和轮心不使用商标纹理'],
        'source_hubs': {str(k): {'center': list(v[0]), 'radius': v[1]} for k, v in hubs.items()}}
    (ROOT/'art/vehicles/elise-source.json').write_text(json.dumps(report, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
    print(json.dumps(report, ensure_ascii=False))


if __name__ == '__main__':
    prepare()
