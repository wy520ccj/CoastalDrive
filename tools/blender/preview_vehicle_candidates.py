"""仅离线观察候选资源的实际几何与材质，不运行下载资源中的脚本。"""

import argparse
import sys
from pathlib import Path

import bpy
from mathutils import Vector

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT/'logs/validation/GARAGE-DESIGN-02-sources'


def capture(name, path, direction):
    if path.suffix == '.blend':
        bpy.ops.wm.open_mainfile(filepath=str(path), load_ui=False, use_scripts=False)
    else:
        bpy.ops.wm.read_factory_settings(use_empty=True)
        bpy.ops.import_scene.gltf(filepath=str(path))
    scene = bpy.context.scene
    meshes = [obj for obj in scene.objects if obj.type == 'MESH']
    points = [obj.matrix_world@Vector(p) for obj in meshes for p in obj.bound_box]
    low = Vector(tuple(min(p[a] for p in points) for a in range(3)))
    high = Vector(tuple(max(p[a] for p in points) for a in range(3)))
    center = (low+high)/2
    scene.render.engine = 'CYCLES'
    scene.cycles.samples = 32
    scene.cycles.use_denoising = True
    scene.render.resolution_x, scene.render.resolution_y = 900, 550
    scene.render.resolution_percentage = 100
    scene.render.image_settings.file_format = 'PNG'
    scene.render.film_transparent = True
    scene.view_settings.view_transform = 'AgX'
    world = bpy.data.worlds.new('candidate-check-hdri')
    world.use_nodes = True
    environment = world.node_tree.nodes.new('ShaderNodeTexEnvironment')
    environment.image = bpy.data.images.load(str(ROOT/'art/vehicles/sources/skylit_garage_2k.hdr'))
    world.node_tree.links.new(environment.outputs['Color'], world.node_tree.nodes['Background'].inputs['Color'])
    world.node_tree.nodes['Background'].inputs['Strength'].default_value = .7
    scene.world = world
    camera = bpy.data.objects.new('candidate-check-camera', bpy.data.cameras.new('candidate-check-camera'))
    scene.collection.objects.link(camera)
    camera.location = center+Vector(direction).normalized()*(high-low).length*1.1
    camera.rotation_euler = (center-camera.location).to_track_quat('-Z', 'Y').to_euler()
    camera.data.lens = 48
    scene.camera = camera
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from render_garage_catalog import fit_catalog_camera

    fit_catalog_camera(scene, camera, meshes)
    scene.render.filepath = str(OUT/(name+'-preview.png'))
    bpy.ops.render.render(write_still=True)
    print(name, tuple(low), tuple(high))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, required=True)
    parser.add_argument('--name', required=True)
    parser.add_argument('--direction', nargs=3, type=float, default=(1, 1.6, .7))
    args = parser.parse_args(sys.argv[sys.argv.index('--')+1:])
    capture(args.name, args.source.resolve(), args.direction)
