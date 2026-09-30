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
        f = rng.uniform(0.95, 1.05)
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
    """连续树冠体积加少量边缘叶团；不把枝端做成互不相连的小球。"""
    objects = []
    lobes = ((0, 0, .36, .82, .70, .46),
             (-.50, -.10, .20, .58, .52, .38),
             (.47, .20, .26, .62, .55, .41),
             (-.12, .43, .26, .58, .56, .39),
             (.12, -.45, .12, .56, .52, .34))
    for j, (x,y,z,sx,sy,sz) in enumerate(lobes):
        loc = (center[0]+x*size, center[1]+y*size, center[2]+z*size)
        objects.append(lump(loc,(size*sx,size*sy,size*sz),1+(j%2),rng))
    for j in range(7):
        angle = j*2.4+rng.random()*.4
        loc = (center[0]+math.cos(angle)*size*.80,
               center[1]+math.sin(angle)*size*.68,
               center[2]+size*rng.uniform(.10,.40))
        objects.append(lump(loc,(size*.28,size*.30,size*.22),1+(j%2),rng,1))
    return objects


def build_tree(seed, crown_only=False):
    rng = random.Random(seed)
    if crown_only:
        return foliage((0,0,.20),2.0,rng)
    height = 4.7+rng.random()*.8
    objects = [branch((0,0,-.12),(.13,.05,height-.4),.22)]
    for j in range(4):
        angle = j*2.4+seed
        end = (math.cos(angle)*1.30,math.sin(angle)*1.10,height-.8+j*.10)
        objects.append(branch((0,0,2.4+j*.30),end,.09))
    objects.extend(foliage((0,0,height-.65),2.3 if seed==117 else 2.0,rng))
    objects.extend(foliage((-.65,.30,height-1.75),1.3,rng))
    return objects


def build_shrub():
    """低矮不规则灌丛；外廓横向相接，根部埋入林下土层。"""
    rng = random.Random(162)
    objects=[]
    for j,(x,y,sx,sy,sz) in enumerate(((-1.30,.16,1.20,.80,.48),
                                       (0,-.12,1.35,1.10,.72),
                                       (1.28,.36,1.12,.88,.53),
                                       (-.50,.85,.85,.76,.46),
                                       (.65,-.79,.96,.65,.38))):
        objects.append(lump((x,y,sz*.60),(sx,sy,sz),1+(j%2),rng))
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
