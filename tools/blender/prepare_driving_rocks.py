"""把已登记的CC0长岩岸加工为适合普通行车视距的短岩坡；保留原UV与材质。"""

import json
from pathlib import Path

import bmesh
import bpy
from mathutils import Matrix, Vector

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / 'art/expressway/candidates/driving-rocks'


def build():
    OUT.mkdir(parents=True, exist_ok=True)
    bpy.ops.wm.read_factory_settings(use_empty=True)
    path = ROOT / 'art/expressway/sources/coastal-scans/coastal_cliff_01/coastal_cliff_01_2k.gltf'
    bpy.ops.import_scene.gltf(filepath=str(path))
    imported = tuple(bpy.context.scene.objects)
    source = next(obj for obj in imported if obj.type == 'MESH')
    original = source.data.copy()
    original.transform(source.matrix_world)
    records = []
    for label, center in zip('abc', (-28., 0., 28.), strict=True):
        mesh = original.copy()
        bm = bmesh.new()
        bm.from_mesh(mesh)
        for x, normal in ((center - 11., (1, 0, 0)), (center + 11., (-1, 0, 0))):
            bmesh.ops.bisect_plane(bm, geom=[*bm.verts, *bm.edges, *bm.faces],
                                  plane_co=Vector((x, 0, 0)), plane_no=Vector(normal),
                                  clear_inner=True, clear_outer=False)
        bm.to_mesh(mesh)
        bm.free()
        mesh.transform(Matrix.Translation((-center, 0, 0)))
        for level, ratio in enumerate((.14, .035, .008)):
            node = bpy.data.objects.new(f'bank-{label}-lod{level}', mesh.copy())
            bpy.context.scene.collection.objects.link(node)
            bpy.context.view_layer.objects.active = node
            modifier = node.modifiers.new('行车视距距离档', 'DECIMATE')
            modifier.ratio = ratio
            bpy.ops.object.modifier_apply(modifier=modifier.name)
            node.data.calc_loop_triangles()
            records.append({'name': node.name, 'source_center_x': center,
                            'crop_width_m': 22, 'triangles': len(node.data.loop_triangles)})
    for obj in imported:
        bpy.data.objects.remove(obj, do_unlink=True)
    bpy.ops.export_scene.gltf(filepath=str(OUT / 'driving-rocks.glb'), export_format='GLB',
                             export_yup=True, export_normals=True, export_cameras=False,
                             export_lights=False, export_animations=False)
    bpy.ops.outliner.orphans_purge(do_recursive=True)
    bpy.ops.file.pack_all()
    bpy.ops.wm.save_as_mainfile(filepath=str(OUT / 'driving-rocks.blend'))
    (OUT / 'source.json').write_text(json.dumps({
        'source': 'Poly Haven coastal_cliff_01, CC0-1.0, existing registered 2K scan',
        'process': 'Three 22m sections; original UV/materials retained; ends embedded in bank; three LODs',
        'models': records,
    }, indent=2), encoding='utf-8')
    print('DRIVING ROCKS READY', len(records), flush=True)


if __name__ == '__main__':
    build()
