"""使用实际车型和实拍HDRI离线渲染车库缩略图、零件与车漆样本。"""

import math
import sys
from pathlib import Path

import bpy
from mathutils import Matrix, Vector

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT/'assets/game/ui/garage-v2'
OUT.mkdir(parents=True, exist_ok=True)


def setup(width, height):
    bpy.ops.wm.read_factory_settings(use_empty=True)
    scene = bpy.context.scene
    scene.render.engine = 'CYCLES'
    scene.cycles.samples = 32
    scene.cycles.use_denoising = True
    scene.render.resolution_x, scene.render.resolution_y = width, height
    scene.render.resolution_percentage = 100
    scene.render.image_settings.file_format = 'PNG'
    scene.render.image_settings.color_mode = 'RGBA'
    scene.render.film_transparent = True
    scene.view_settings.view_transform = 'AgX'
    world = bpy.data.worlds.new('Poly Haven Skylit Garage · Greg Zaal · CC0')
    world.use_nodes = True
    tree = world.node_tree
    environment = tree.nodes.new('ShaderNodeTexEnvironment')
    environment.image = bpy.data.images.load(str(ROOT/'art/vehicles/sources/skylit_garage_2k.hdr'))
    tree.links.new(environment.outputs['Color'], tree.nodes['Background'].inputs['Color'])
    tree.nodes['Background'].inputs['Strength'].default_value = .7
    scene.world = world
    data = bpy.data.cameras.new('catalog-camera')
    camera = bpy.data.objects.new('catalog-camera', data)
    scene.collection.objects.link(camera)
    scene.camera = camera
    return scene, camera


def aim(camera, point, distance, direction=(1, 1.6, .8)):
    target = Vector(point)
    camera.location = target+Vector(direction).normalized()*distance
    camera.rotation_euler = (target-camera.location).to_track_quat('-Z', 'Y').to_euler()
    camera.data.lens = 48


def bounds(objects):
    points = [obj.matrix_world@Vector(p) for obj in objects if obj.type == 'MESH' for p in obj.bound_box]
    low = Vector(tuple(min(p[i] for p in points) for i in range(3)))
    high = Vector(tuple(max(p[i] for p in points) for i in range(3)))
    return low, high


def output(scene, name):
    scene.render.filepath = str(OUT/(name+'.png'))
    bpy.ops.render.render(write_still=True)


def import_car(path):
    bpy.ops.import_scene.gltf(filepath=str(path))
    for name in ('License Plate', 'InteriorSteeringEmblem'):
        obj = bpy.data.objects.get(name)
        if obj is not None:
            bpy.data.objects.remove(obj, do_unlink=True)
    if path.name == 'CarConcept.glb':
        for mat in bpy.data.materials:
            if not mat.use_nodes:
                continue
            for node in mat.node_tree.nodes:
                if node.type != 'BSDF_PRINCIPLED':
                    continue
                if mat.name in ('Hardware', 'Rim1', 'Rim2', 'Mirror', 'Brake', 'Material_2'):
                    for link in list(node.inputs['Emission Color'].links):
                        mat.node_tree.links.remove(link)
                    node.inputs['Emission Strength'].default_value = 0
                if mat.name == 'Tireside':
                    for field in ('Base Color', 'Normal'):
                        for link in list(node.inputs[field].links):
                            mat.node_tree.links.remove(link)
                    node.inputs['Base Color'].default_value = (.02, .02, .02, 1)
        for name in ('WheelFrontL', 'WheelFrontR'):
            wheel = bpy.data.objects[name]
            axle = wheel.matrix_world.to_3x3()@Vector((1, 0, 0))
            center = wheel.matrix_world.translation.copy()
            correction = Matrix.Translation(center)@Matrix.Rotation(-math.atan2(axle.y, axle.x), 4, 'Z')@Matrix.Translation(-center)
            wheel.matrix_world = correction@wheel.matrix_world
    return [obj for obj in bpy.context.scene.objects if obj.type == 'MESH']


def render_shadow(name, path, scale=1.):
    scene, camera = setup(512, 512)
    objects = import_car(path)
    bpy.context.view_layer.update()
    low, _ = bounds(objects)
    for root in (obj for obj in scene.objects if obj.parent is None and obj.type != 'CAMERA'):
        root.scale *= scale
        root.location *= scale
        root.location.z -= low.z*scale
    for obj in objects:
        obj.visible_camera = False
    bpy.ops.mesh.primitive_plane_add(size=8)
    bpy.context.object.is_shadow_catcher = True
    camera.data.type = 'ORTHO'
    camera.data.ortho_scale = 8
    aim(camera, (0, 0, 0), 10, (0, 0, 1))
    output(scene, name)


def main():
    selected = sys.argv[sys.argv.index('--')+1:] if '--' in sys.argv else []
    for name, filename in (('game-tuned', 'classic_coupe_v1.glb'), ('coastal-hatch', 'coastal_hatch.glb'),
                           ('coastal-roadster', 'coastal_roadster.glb'),
                           ('gr86-2022-premium-6mt', 'gr86_2022_premium.glb'),
                           ('coastal-gt', None), ('club-coupe', 'club_coupe.glb')):
        if selected and name not in selected:
            continue
        scene, camera = setup(384, 216)
        if name == 'club-coupe':
            path = ROOT/'art/vehicles/club_coupe.glb'
        else:
            path = ROOT/'assets/game/vehicles'/filename if filename else ROOT/'art/vehicles/sources/car-concept/CarConcept.glb'
        objects = import_car(path)
        bpy.context.view_layer.update()
        low, high = bounds(objects)
        aim(camera, (low+high)/2, (high-low).length*1.1,
            (-1, -1.6, .8) if filename is None else (1, 1.6, .8))
        output(scene, 'car-'+name)
    if selected:
        if 'club-coupe' in selected:
            render_shadow('contact-shadow-club-coupe', ROOT/'art/vehicles/club_coupe.glb', .75)
        return
    for name, object_name in (('tire', 'WheelFrontL'), ('brake', 'WheelFrontLBrakeDisc')):
        scene, camera = setup(320, 320)
        import_car(ROOT/'art/vehicles/sources/car-concept/CarConcept.glb')
        root = bpy.data.objects[object_name]
        objects = [root, *root.children_recursive]
        for obj in bpy.context.scene.objects:
            if obj.type == 'MESH' and obj not in objects:
                obj.hide_render = True
        bpy.context.view_layer.update()
        low, high = bounds(objects)
        aim(camera, (low+high)/2, (high-low).length*1.05, (1.7, 1., .55))
        output(scene, name)
    colors = ((.90, .43, .10), (.12, .45, .78), (.78, .08, .055), (.16, .46, .28), (.85, .87, .86))
    for index, color in enumerate(colors):
        scene, camera = setup(256, 256)
        bpy.ops.mesh.primitive_uv_sphere_add(segments=64, ring_count=48, radius=1)
        sphere = bpy.context.object
        for face in sphere.data.polygons:
            face.use_smooth = True
        material = bpy.data.materials.new('car-paint-sample')
        material.use_nodes = True
        shader = material.node_tree.nodes['Principled BSDF']
        shader.inputs['Base Color'].default_value = (*(c/12.92 if c <= .04045 else ((c+.055)/1.055)**2.4 for c in color), 1)
        shader.inputs['Metallic'].default_value = .45
        shader.inputs['Roughness'].default_value = .23
        shader.inputs['Coat Weight'].default_value = 1.
        sphere.data.materials.append(material)
        aim(camera, (0, 0, 0), 3.7)
        output(scene, 'paint-'+str(index))
    render_shadow('contact-shadow', ROOT/'art/vehicles/sources/car-concept/CarConcept.glb')
    render_shadow('contact-shadow-club-coupe', ROOT/'art/vehicles/club_coupe.glb', .75)


if __name__ == '__main__':
    main()
