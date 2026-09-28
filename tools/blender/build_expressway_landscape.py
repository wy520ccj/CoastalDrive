"""原创快速路阔叶植被与岩层；保存可编辑Blender并导出GLB。"""

import hashlib
import json
import math
import random
from pathlib import Path

import bpy
from mathutils import Vector

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "assets/game/expressway"
BLEND = ROOT / "art/expressway/expressway_landscape.blend"
bpy.ops.object.select_all(action="SELECT")
bpy.ops.object.delete(use_global=False)
PALETTE = ((0.065, 0.145, 0.036, 1), (0.12, 0.235, 0.063, 1),
           (0.205, 0.31, 0.083, 1), (0.29, 0.37, 0.125, 1),
           (0.22, 0.145, 0.078, 1), (0.46, 0.41, 0.32, 1))
MATERIALS = []
for i, color in enumerate(PALETTE):
    mat = bpy.data.materials.new(f"Expressway-{i}")
    mat.diffuse_color = color
    mat.use_nodes = True
    shader = mat.node_tree.nodes.get("Principled BSDF")
    shader.inputs["Base Color"].default_value = color
    shader.inputs["Roughness"].default_value = 0.92
    MATERIALS.append(mat)
rock_mat = MATERIALS[-1]
tex = rock_mat.node_tree.nodes.new("ShaderNodeTexImage")
tex.image = bpy.data.images.load(str(OUT / "strata-albedo.png"))
rock_mat.node_tree.links.new(tex.outputs["Color"], rock_mat.node_tree.nodes.get("Principled BSDF").inputs["Base Color"])


def lump(loc, scale, material, rng, subdivisions=2):
    bpy.ops.mesh.primitive_ico_sphere_add(subdivisions=subdivisions, radius=1, location=loc)
    obj = bpy.context.object
    for vertex in obj.data.vertices:
        p = vertex.co
        f = rng.uniform(0.86, 1.14)
        p.x *= scale[0] * f
        p.y *= scale[1] * f
        p.z *= scale[2] * f
    obj.data.materials.append(MATERIALS[material])
    for poly in obj.data.polygons:
        poly.use_smooth = True
    return obj


def branch(a, b, radius):
    a, b = Vector(a), Vector(b)
    bpy.ops.mesh.primitive_cone_add(vertices=8, radius1=radius, radius2=radius * 0.35,
                                   depth=(b - a).length, location=(a + b) / 2)
    obj = bpy.context.object
    obj.rotation_mode = "QUATERNION"
    obj.rotation_quaternion = Vector((0, 0, 1)).rotation_difference((b - a).normalized())
    obj.data.materials.append(MATERIALS[4])
    return obj


def foliage(center, size, rng):
    objects = []
    centers = []
    for j in range(8):
        angle = j * 2.4
        radius = size * (0.20 + .46 * rng.random())
        loc = (center[0] + math.cos(angle) * radius,
               center[1] + math.sin(angle) * radius,
               center[2] + size * (.20 + .70 * rng.random()))
        centers.append(loc)
        objects.append(lump(loc, (size * .43, size * .39, size * .46), j % 3, rng))
    verts, faces, colors = [], [], []
    for j in range(160):
        base = Vector(centers[j % len(centers)])
        a = rng.random() * math.tau
        z = rng.uniform(-1, 1)
        r = math.sqrt(1 - z * z)
        normal = Vector((r * math.cos(a), r * math.sin(a), z))
        pos = base + normal * size * .43
        tangent = normal.cross(Vector((0, 0, 1)))
        if tangent.length < .01:
            tangent = Vector((1, 0, 0))
        tangent.normalize()
        bitangent = normal.cross(tangent).normalized()
        length = size * rng.uniform(.10, .18)
        offset = len(verts)
        verts.extend(tuple(v) for v in (pos + tangent * length,
                      pos + bitangent * length * .55, pos - tangent * length,
                      pos - bitangent * length * .55, pos + normal * length * .2))
        faces.extend((offset + k, offset + (k + 1) % 4, offset + 4) for k in range(4))
        colors.extend([1 + (j % 3)] * 4)
    mesh = bpy.data.meshes.new("individual-leaf-sprays")
    mesh.from_pydata(verts, [], faces)
    for mat in MATERIALS[:4]:
        mesh.materials.append(mat)
    for face, color in zip(mesh.polygons, colors):
        face.material_index = color
    leaves = bpy.data.objects.new("leaf-sprays", mesh)
    bpy.context.collection.objects.link(leaves)
    objects.append(leaves)
    return objects


def build_tree(seed, crown_only=False):
    rng = random.Random(seed)
    objects = []
    if crown_only:
        return foliage((0, 0, .1), 1.6, rng)
    height = 4.8 + rng.random()
    objects.append(branch((0, 0, 0), (.10, .06, height), .19))
    for j in range(5):
        a = j * 2.4 + seed
        reach = 1.15 + rng.random() * .7
        end = (math.cos(a) * reach, math.sin(a) * reach, height - 2.1 + j * .48)
        objects.append(branch((0, 0, 2.2 + j * .33), end, .075))
        objects.extend(foliage(end, .9 + rng.random() * .25, rng))
    return objects


def build_shrub():
    rng = random.Random(162)
    objects = []
    for x, y, size in ((-1.65, .1, .9), (0, -.15, 1.1), (1.6, .2, .8)):
        objects.extend(foliage((x, y, 0), size, rng))
    return objects


def build_rocks():
    rng = random.Random(329)
    objects = []
    for j in range(5):
        obj = lump((-.12 * j, .15 * j, -.08 + j * .34),
                   (3.4 - j * .32, 1.8 - j * .13, .32), 5, rng, 2)
        for poly in obj.data.polygons:
            poly.use_smooth = False
        uv = obj.data.uv_layers.new(name="UVMap")
        for loop in obj.data.loops:
            p = obj.data.vertices[loop.vertex_index].co + obj.location
            uv.data[loop.index].uv = ((p.x + p.y * .3) / 3, p.z / 2)
        objects.append(obj)
    return objects


assets = []
for name, objects in (("broadleaf-a", build_tree(117)), ("broadleaf-b", build_tree(287)),
                      ("fine-crown", build_tree(46, True)),
                      ("fine-shrubs", build_shrub()), ("strata-shelf", build_rocks())):
    bpy.ops.object.select_all(action="DESELECT")
    for obj in objects:
        obj.select_set(True)
    bpy.context.view_layer.objects.active = objects[0]
    bpy.ops.object.join()
    obj = bpy.context.object
    obj.name = name
    bpy.context.scene.cursor.location = (0, 0, 0)
    bpy.ops.object.origin_set(type="ORIGIN_CURSOR")
    bpy.ops.object.transform_apply(location=False, rotation=True, scale=True)
    obj["source"] = "Original HWY-01 Blender geometry; deterministic editable script"
    path = OUT / f"{name}.glb"
    bpy.ops.export_scene.gltf(filepath=str(path), export_format="GLB", use_selection=True,
                              export_apply=True, export_yup=True)
    assets.append({"name": name, "file": path.name,
                   "triangles": sum(len(p.vertices) - 2 for p in obj.data.polygons),
                   "sha256": hashlib.sha256(path.read_bytes()).hexdigest()})
    obj.location = (len(assets) * 9, 0, 0)
bpy.ops.file.pack_all()
bpy.ops.wm.save_as_mainfile(filepath=str(BLEND))
(OUT / "landscape-manifest.json").write_text(json.dumps({
    "source": "tools/blender/build_expressway_landscape.py",
    "editable_blend": "art/expressway/expressway_landscape.blend",
    "blender": bpy.app.version_string,
    "rights": "Original project geometry; AI-generated grass and strata albedo artwork",
    "assets": assets,
}, indent=2), encoding="utf-8")
print("EXPRESSWAY_LANDSCAPE_EXPORTED", assets)
