"""为完整CC0岩岸保留轮廓与源材质，制作三个距离档；不改碰撞地形。"""

import json
from pathlib import Path

import bpy

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / 'art/expressway/candidates/coastal-rocks'


def build():
    OUT.mkdir(parents=True, exist_ok=True)
    bpy.ops.wm.read_factory_settings(use_empty=True)
    records = []
    for asset, label in (('coastal_cliff_01', 'cliff'), ('coast_rocks_01', 'shore')):
        before = set(bpy.context.scene.objects)
        path = ROOT / f'art/expressway/sources/coastal-scans/{asset}/{asset}_2k.gltf'
        bpy.ops.import_scene.gltf(filepath=str(path))
        imported = set(bpy.context.scene.objects) - before
        source = next(obj for obj in imported if obj.type == 'MESH')
        for level, ratio in enumerate((.2, .05, .01)):
            obj = bpy.data.objects.new(f'{label}-lod{level}', source.data.copy())
            bpy.context.scene.collection.objects.link(obj)
            obj.matrix_world = source.matrix_world.copy()
            bpy.context.view_layer.objects.active = obj
            modifier = obj.modifiers.new('岩岸距离档', 'DECIMATE')
            modifier.ratio = ratio
            bpy.ops.object.modifier_apply(modifier=modifier.name)
            obj.data.calc_loop_triangles()
            records.append({'name': obj.name, 'triangles': len(obj.data.loop_triangles), 'ratio': ratio})
        for obj in imported:
            bpy.data.objects.remove(obj, do_unlink=True)
    bpy.ops.export_scene.gltf(filepath=str(OUT / 'coastal-rocks.glb'), export_format='GLB',
                             export_yup=True, export_normals=True, export_cameras=False,
                             export_lights=False, export_animations=False)
    bpy.ops.outliner.orphans_purge(do_recursive=True)
    bpy.ops.file.pack_all()
    bpy.ops.wm.save_as_mainfile(filepath=str(OUT / 'coastal-rocks.blend'))
    (OUT / 'rocks.json').write_text(json.dumps(records, indent=2) + '\n', encoding='utf-8')
    print('COASTAL ROCKS', json.dumps(records), flush=True)


if __name__ == '__main__':
    build()
