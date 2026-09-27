import json
import math
import random
from pathlib import Path

import bpy
from mathutils import Matrix, Vector

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "assets/game/environment/models"
BLEND = ROOT / "art/coastal/coastal_kit.blend"
MANIFEST = ROOT / "assets/game/environment/kit-manifest.json"
random.seed(71824)

# 统一颜色与粗糙度，匹配明亮的海岸场景。
COLORS = {
    "pine": (0.13, 0.23, 0.09, 1),
    "pine_light": (0.25, 0.34, 0.13, 1),
    "sage": (0.42, 0.47, 0.25, 1),
    "leaf": (0.27, 0.35, 0.12, 1),
    "bark": (0.30, 0.20, 0.13, 1),
    "stone": (0.36, 0.37, 0.28, 1),
    "stone_dark": (0.24, 0.25, 0.19, 1),
    "stone_light": (0.48, 0.48, 0.36, 1),
    "sand": (0.53, 0.49, 0.32, 1),
    "cream": (0.88, 0.83, 0.71, 1),
    "white": (0.91, 0.87, 0.77, 1),
    "terra": (0.64, 0.22, 0.13, 1),
    "terra_light": (0.78, 0.32, 0.19, 1),
    "navy": (0.07, 0.17, 0.22, 1),
    "sea": (0.10, 0.34, 0.40, 1),
    "glass": (0.12, 0.28, 0.32, 1),
    "gold": (0.91, 0.60, 0.21, 1),
    "metal": (0.22, 0.28, 0.29, 1),
    "flower": (0.92, 0.73, 0.32, 1),
}


def material(name):
    m = bpy.data.materials.get("Coast_" + name)
    if m is None:
        m = bpy.data.materials.new("Coast_" + name)
        m.diffuse_color = COLORS[name]
        m.use_nodes = True
        p = m.node_tree.nodes.get("Principled BSDF")
        p.inputs["Base Color"].default_value = COLORS[name]
        p.inputs["Roughness"].default_value = 0.85
        p.inputs["Metallic"].default_value = 0.0
    return m


def mat(obj, name):
    obj.data.materials.clear()
    obj.data.materials.append(material(name))


def cube(name, loc, scale, color, bevel=0):
    bpy.ops.mesh.primitive_cube_add(size=1, location=loc)
    o = bpy.context.object
    o.name = name
    o.dimensions = scale
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    mat(o, color)
    if bevel:
        mod = o.modifiers.new("Soft stone edges", "BEVEL")
        mod.width = bevel
        mod.segments = 1
        bpy.context.view_layer.objects.active = o
        bpy.ops.object.modifier_apply(modifier=mod.name)
    return o


def cylinder(name, loc, radius, depth, color, vertices=10, radius2=None):
    if radius2 is None:
        bpy.ops.mesh.primitive_cylinder_add(
            vertices=vertices, radius=radius, depth=depth, location=loc
        )
    else:
        bpy.ops.mesh.primitive_cone_add(
            vertices=vertices, radius1=radius, radius2=radius2, depth=depth, location=loc
        )
    o = bpy.context.object
    o.name = name
    mat(o, color)
    return o


def sphere(name, loc, scale, color, seed, subdivisions=1):
    bpy.ops.mesh.primitive_ico_sphere_add(subdivisions=subdivisions, radius=1, location=loc)
    o = bpy.context.object
    o.name = name
    rng = random.Random(seed)
    for v in o.data.vertices:
        f = rng.uniform(0.82, 1.18)
        v.co.x *= scale[0] * f
        v.co.y *= scale[1] * f
        v.co.z *= scale[2] * f
    mat(o, color)
    return o


def branch_between(name, start, end, radius, color):
    a = Vector(start)
    b = Vector(end)
    delta = b - a
    o = cylinder(name, (a + b) / 2, radius, delta.length, color, 6, radius2=radius * 0.18)
    o.rotation_mode = "QUATERNION"
    o.rotation_quaternion = Vector((0, 0, 1)).rotation_difference(delta.normalized())
    return o


def mesh_object(name, verts, faces, color):
    me = bpy.data.meshes.new(name + "_mesh")
    me.from_pydata(verts, [], faces)
    me.materials.append(material(color))
    me.update()
    o = bpy.data.objects.new(name, me)
    bpy.context.collection.objects.link(o)
    return o


def ring_rail(name, radius, z, tube_radius, color, sides=16, tube_sides=5):
    """创建不遮挡灯笼玻璃的圆形栏杆管。"""
    verts = []
    faces = []
    for i in range(sides):
        a = math.tau * i / sides
        center = Vector((radius * math.cos(a), radius * math.sin(a), z))
        radial = Vector((math.cos(a), math.sin(a), 0))
        for j in range(tube_sides):
            b = math.tau * j / tube_sides
            p = center + tube_radius * (math.cos(b) * radial + Vector((0, 0, math.sin(b))))
            verts.append(tuple(p))
    for i in range(sides):
        for j in range(tube_sides):
            a = i * tube_sides + j
            b = i * tube_sides + (j + 1) % tube_sides
            c = ((i + 1) % sides) * tube_sides + (j + 1) % tube_sides
            d = ((i + 1) % sides) * tube_sides + j
            faces.append((a, b, c, d))
    return mesh_object(name, verts, faces, color)


def build_asset(name, description, source, license_text, target_height, builder, variant=0):
    bpy.ops.object.select_all(action="DESELECT")
    collection = bpy.data.collections.new(name)
    bpy.context.scene.collection.children.link(collection)
    bpy.context.view_layer.active_layer_collection = (
        bpy.context.view_layer.layer_collection.children[collection.name]
    )
    before = set(bpy.data.objects)
    builder(variant)
    objects = [o for o in bpy.data.objects if o not in before and o.type == "MESH"]
    bpy.ops.object.select_all(action="DESELECT")
    for obj in objects:
        obj.select_set(True)
    bpy.context.view_layer.objects.active = objects[0]
    bpy.ops.object.join()
    obj = bpy.context.object
    obj.name = name
    # 先将完整世界变换写入网格，再统一局部原点，确保 GLB 底面落在 Z=0。
    obj.data.transform(obj.matrix_world)
    obj.matrix_world = Matrix.Identity(4)
    xs = [v.co.x for v in obj.data.vertices]
    ys = [v.co.y for v in obj.data.vertices]
    zs = [v.co.z for v in obj.data.vertices]
    cx = (min(xs) + max(xs)) / 2
    cy = (min(ys) + max(ys)) / 2
    bottom = min(zs)
    for vertex in obj.data.vertices:
        vertex.co.x -= cx
        vertex.co.y -= cy
        vertex.co.z -= bottom
    height = max(v.co.z for v in obj.data.vertices)
    for vertex in obj.data.vertices:
        vertex.co.z *= target_height / height
    obj.location = (0, 0, 0)
    obj["asset_id"] = name
    obj["description"] = description
    obj["source"] = source
    for current_collection in list(obj.users_collection):
        current_collection.objects.unlink(obj)
    collection.objects.link(obj)
    bpy.context.view_layer.update()
    # 编辑场景按网格排列；单体 GLB 导出时会恢复原点位置。
    index = len(assets)
    obj.location = ((index % 4) * 8.0, (index // 4) * 10.0, 0)
    obj["source_note"] = source
    obj["license_note"] = license_text
    obj["origin"] = "Ground center (Blender Z=0)"
    obj["target_height_m"] = target_height
    assets.append(
        {
            "object": obj,
            "name": name,
            "description": description,
            "source": source,
            "license": license_text,
            "target_height_m": target_height,
        }
    )
    return obj


# 使用低模几何，并通过错位轮廓和建筑细节形成差异。
def pine_builder(v):
    # 枝冠向侧面伸展并互相搭接，保留树干与林缘空隙。
    height = 7.5 + v * 0.8
    rng = random.Random(510 + v)
    cylinder("tapered trunk", (0, 0, height / 2), 0.25, height, "bark", 9, 0.045)
    for tier in range(6):
        t = tier / 5
        z = 2.1 + t * (height - 2.6)
        reach = 1.65 * (1 - 0.76 * t)
        phase = tier * 1.73 + v * 0.4
        sphere(
            "central needle crown",
            (0, 0, z + 0.35),
            (reach * 0.88, reach * 0.88, 0.85 - 0.25 * t),
            "pine",
            820 + tier,
            2,
        )
        for j in range(5):
            angle = phase + math.tau * j / 5 + rng.uniform(-0.15, 0.15)
            length = reach * rng.uniform(0.8, 1.12)
            x, y = math.cos(angle) * length, math.sin(angle) * length
            branch_between(
                "spreading bough", (0, 0, z - 0.38), (x, y, z), 0.08 * (1 - t * 0.6), "bark"
            )
            crown = sphere(
                "overlapping needle spray",
                (x, y, z + rng.uniform(-0.14, 0.18)),
                (1.1 * (1 - t * 0.65), 0.78 * (1 - t * 0.6), 0.58 - 0.17 * t),
                "pine_light" if j == 1 else "pine",
                910 + tier * 5 + j + v * 100,
                2,
            )
            crown.rotation_euler.z = angle


def bush_builder(v):
    clumps = [
        (-0.34, -0.04, 0.40, (0.49, 0.40, 0.42)),
        (0.16, -0.12, 0.48, (0.55, 0.48, 0.50)),
        (0.48, 0.12, 0.38, (0.42, 0.38, 0.40)),
        (-0.03, 0.22, 0.62, (0.40, 0.38, 0.52)),
        (-0.40, 0.22, 0.30, (0.34, 0.32, 0.33)),
        (0.29, -0.25, 0.28, (0.37, 0.30, 0.31)),
        (0.07, 0.04, 0.72, (0.34, 0.31, 0.39)),
    ]
    for i, (x, y, z, sc) in enumerate(clumps):
        sphere(
            "irregular leaf mass",
            (x, y, z),
            sc,
            ["sage", "leaf", "pine_light"][i % 3],
            100 + v * 17 + i,
            2,
        )


def rock_builder(v):
    # 連續錯位環層形成破碎石灰岩質量，材質隨高度由暗岩過渡到苔色頂面。
    h = 1.80 if v == 0 else 1.65
    sides = 11
    levels = [(0.02, 0.85), (0.28, 1.00), (0.76, 0.98), (1.22, 0.86), (h, 0.64)]
    rng = random.Random(201 + v)
    phase = rng.uniform(-0.1, 0.1)
    radial = [rng.uniform(0.82, 1.15) for _ in range(sides)]
    verts = []
    for level, (z, scale) in enumerate(levels):
        for i in range(sides):
            a = math.tau * i / sides + phase + 0.035 * level
            wobble = radial[i] * rng.uniform(0.96, 1.04)
            zz = z + (0 if level in (0, len(levels) - 1) else rng.uniform(-0.10, 0.10))
            verts.append(
                (1.48 * scale * wobble * math.cos(a), 1.06 * scale * wobble * math.sin(a), zz)
            )
    faces, indices = [], []
    for level in range(len(levels) - 1):
        for i in range(sides):
            a = level * sides + i
            b = level * sides + (i + 1) % sides
            c = (level + 1) * sides + (i + 1) % sides
            d = (level + 1) * sides + i
            faces.extend(((a, b, c), (a, c, d)))
            if level == 0:
                indices.extend((0, 0 if i % 3 else 1))
            elif level == 1:
                indices.extend((1, 1))
            elif level == 2:
                indices.extend((2 if i % 3 else 1, 2))
            else:
                indices.extend((3, 3 if i % 2 else 2))
    faces.append(tuple(reversed(range(sides))))
    indices.append(0)
    top = len(verts)
    verts.append((rng.uniform(-0.12, 0.12), rng.uniform(-0.1, 0.1), h))
    for i in range(sides):
        faces.append(
            ((len(levels) - 1) * sides + i, (len(levels) - 1) * sides + (i + 1) % sides, top)
        )
        indices.append(4)
    rock = mesh_object("connected fractured limestone mass", verts, faces, "stone_dark")
    for name in ("stone", "stone_light", "sand", "sage"):
        rock.data.materials.append(material(name))
    for poly, index in zip(rock.data.polygons, indices):
        poly.material_index = index


def flowers_builder(v):
    for i, (x, y, h) in enumerate(
        [(-0.25, -0.12, 0.55), (0.18, -0.06, 0.72), (0.38, 0.20, 0.48), (-0.04, 0.27, 0.63)]
    ):
        cylinder("stem", (x, y, h / 2), 0.018, h, "leaf", 6)
        sphere("leaf", (x - 0.12, y, h * 0.45), (0.17, 0.045, 0.07), "sage", 310 + i, 1)
        sphere("flower center", (x, y, h + 0.035), (0.075, 0.075, 0.06), "gold", 320 + i, 1)
        for k in range(5):
            a = k * math.tau / 5
            sphere(
                "petal",
                (x + math.cos(a) * 0.085, y + math.sin(a) * 0.085, h + 0.03),
                (0.055, 0.035, 0.04),
                "flower",
                330 + i * 5 + k,
                1,
            )


def cliff_builder(v):
    # 连续岩体向上收窄，并保留较平的顶部。
    sides = 12
    levels = [
        (0.04, 1.00, 1.00),
        (0.78, 0.98, 0.94),
        (1.62, 0.84, 0.82),
        (2.48, 0.68, 0.70),
        (3.12, 0.55, 0.57),
    ]
    verts = []
    rng = random.Random(860 + v)
    angle_jitter = [rng.uniform(-0.07, 0.07) for _ in range(sides)]
    radial = [rng.uniform(0.88, 1.12) for _ in range(sides)]
    for level, (z, sx, sy) in enumerate(levels):
        for i in range(sides):
            a = math.tau * i / sides + angle_jitter[i]
            r = radial[i] * (1 + 0.05 * math.sin(i * 2.3 + level * 0.8))
            # 顶圈保持平整，便于放置灯塔。
            zz = z if level == len(levels) - 1 else z + rng.uniform(-0.07, 0.07)
            verts.append((3.0 * sx * r * math.cos(a), 2.15 * sy * r * math.sin(a), zz))
    faces = []
    face_material = []
    for level in range(len(levels) - 1):
        for i in range(sides):
            a = level * sides + i
            b = level * sides + (i + 1) % sides
            c = (level + 1) * sides + (i + 1) % sides
            d = (level + 1) * sides + i
            # 交错三角面表现岩壁断裂层次。
            if (i + level) % 2:
                faces.extend([(a, b, d), (b, c, d)])
            else:
                faces.extend([(a, b, c), (a, c, d)])
            shade = 1 if (i + 2 * level) % 5 == 0 else (2 if level == 2 and i % 4 == 0 else 0)
            face_material.extend([shade, shade])
    # 封闭底面，并以草地材质覆盖平顶。
    faces.append(tuple(reversed(range(sides))))
    face_material.append(0)
    center = len(verts)
    verts.append((0.03, -0.02, 3.12))
    top_start = (len(levels) - 1) * sides
    for i in range(sides):
        faces.append((top_start + i, top_start + (i + 1) % sides, center))
        face_material.append(3)
    rock = mesh_object("continuous tapered coastal rock", verts, faces, "stone")
    rock.data.materials.append(material("stone_light"))
    rock.data.materials.append(material("sand"))
    rock.data.materials.append(material("sage"))
    for poly, index in zip(rock.data.polygons, face_material):
        poly.material_index = index


def lighthouse_builder(v):
    # 约 14 米高的渐收石塔，保留清晰的道路尺度细节。
    cylinder("footing", (0, 0, 0.30), 1.35, 0.60, "sand", 12)
    cylinder("tower", (0, 0, 6.1), 1.03, 11.2, "white", 12, 0.67)
    cylinder("lower cornice", (0, 0, 1.0), 1.14, 0.18, "terra", 12)
    cylinder("upper cornice", (0, 0, 11.55), 0.83, 0.28, "terra", 12)
    cylinder("lantern floor", (0, 0, 11.8), 0.88, 0.22, "navy", 12)
    cylinder("lantern glazing", (0, 0, 12.35), 0.69, 0.90, "glass", 12)
    cylinder("lantern rim", (0, 0, 12.82), 0.80, 0.16, "terra", 12)
    # 塔顶屋面留出檐口。
    cylinder("lantern roof", (0, 0, 13.28), 0.84, 0.78, "terra_light", 12, 0.10)
    cylinder("finial", (0, 0, 13.77), 0.11, 0.20, "gold", 8, 0.04)
    # 塔身窗格与灯廊护栏采用重复构件。
    # 門和窗緊貼錐形塔面，向外微凸以免被牆體遮住。
    cube("tower entry door", (0, -1.00, 1.18), (0.54, 0.04, 1.55), "navy", 0.025)
    for z in (4.7, 6.9, 9.1):
        radius = 1.03 - (z - 0.5) * (0.36 / 11.2) - 0.018
        for i in range(8):
            a = math.tau * i / 8
            x, y = radius * math.cos(a), radius * math.sin(a)
            # 窄矩形窗依塔身切線方向旋轉，材質面朝外。
            o = cube("flush tower window", (x, y, z), (0.16, 0.04, 0.58), "sea")
            o.rotation_euler[2] = a - math.pi / 2
    sphere("door handle", (0.17, -1.025, 1.14), (0.035, 0.025, 0.035), "gold", 942)
    for i in range(16):
        a = math.tau * i / 12
        cylinder(
            "lantern rail post",
            (math.cos(a) * 0.91, math.sin(a) * 0.91, 12.12),
            0.035,
            0.58,
            "navy",
            6,
        )
    ring_rail("gallery upper handrail", 0.91, 12.42, 0.035, "navy")
    ring_rail("gallery lower rail", 0.91, 11.96, 0.026, "navy")


def house_builder(v):
    # 约 5.6 x 5 米，占地和檐口比例清晰，屋脊带外挑瓦面。
    cube("stone plinth", (0, 0, 0.18), (5.6, 5.0, 0.36), "sand", 0.08)
    cube("limewashed walls", (0, 0, 2.05), (5.1, 4.5, 3.45), "cream", 0.04)
    # 山墙朝向前后，屋脊沿 Y 轴。
    verts = [
        (-2.55, -2.25, 3.77),
        (2.55, -2.25, 3.77),
        (0, -2.25, 5.15),
        (-2.55, 2.25, 3.77),
        (2.55, 2.25, 3.77),
        (0, 2.25, 5.15),
    ]
    mesh_object("gable ends", verts, [(0, 1, 2), (3, 5, 4), (0, 2, 5, 3), (1, 4, 5, 2)], "cream")
    # 两片厚实的陶瓦坡面。
    mesh_object(
        "terracotta roof",
        [
            (-2.95, -2.7, 3.78),
            (0, -2.7, 5.38),
            (0, 2.7, 5.38),
            (-2.95, 2.7, 3.78),
            (2.95, -2.7, 3.78),
            (2.95, 2.7, 3.78),
        ],
        [(0, 1, 2, 3), (1, 4, 5, 2)],
        "terra",
    )
    ridge = cylinder("ridge cap", (0, 0, 5.38), 0.15, 5.65, "terra_light", 8)
    ridge.rotation_euler[0] = math.pi / 2
    # 正面设置门、窗台和带百叶的深色窗。
    cube("front door", (0, -2.29, 1.22), (1.05, 0.12, 2.18), "navy", 0.04)
    cube("door inset", (0, -2.37, 1.25), (0.72, 0.035, 1.75), "sea")
    sphere("door handle", (0.36, -2.42, 1.2), (0.06, 0.035, 0.06), "gold", 420)
    for x in (-1.55, 1.55):
        cube("window recess", (x, -2.30, 2.43), (0.98, 0.12, 1.20), "navy")
        cube("window glass", (x, -2.38, 2.44), (0.75, 0.035, 0.94), "sea")
        cube("window mullion", (x, -2.41, 2.44), (0.07, 0.03, 0.94), "cream")
        cube("window sill", (x, -2.39, 1.80), (1.15, 0.22, 0.12), "white")
        for dx in (-0.61, 0.61):
            cube("shutter", (x + dx, -2.34, 2.42), (0.20, 0.10, 1.28), "terra_light")
    # 侧面烟囱与双柱门廊。
    cube("chimney", (1.55, 0.85, 4.65), (0.55, 0.65, 1.65), "terra", 0.05)
    cube("chimney cap", (1.55, 0.85, 5.48), (0.75, 0.82, 0.17), "terra_light")
    cube("porch canopy", (0, -2.95, 3.10), (2.5, 1.25, 0.18), "terra", 0.04)
    for x in (-1.05, 1.05):
        cylinder("porch column", (x, -3.25, 1.70), 0.10, 2.8, "white", 8)


def sign_builder(v):
    cylinder("post", (0, 0, 1.05), 0.07, 2.1, "metal", 8)
    cube("sign back", (0, -0.04, 1.55), (1.20, 0.14, 0.72), "cream", 0.04)
    # 箭头多边形朝局部 +X 方向。
    verts = [
        (-0.40, -0.13, 1.40),
        (0.05, -0.13, 1.40),
        (0.05, -0.13, 1.27),
        (0.43, -0.13, 1.55),
        (0.05, -0.13, 1.83),
        (0.05, -0.13, 1.70),
        (-0.40, -0.13, 1.70),
    ]
    mesh_object("blue chevron", verts, [(0, 1, 2, 3, 4, 5, 6)], "navy")
    cube("reflective border", (0, -0.14, 1.55), (1.28, 0.035, 0.80), "gold")
    cube("sign face", (0, -0.17, 1.55), (1.20, 0.04, 0.72), "cream")
    # 在牌面前侧重建箭头。
    mesh_object(
        "direction chevron",
        [(x, y - 0.075, z) for x, y, z in verts],
        [(0, 1, 2, 3, 4, 5, 6)],
        "sea",
    )


def lamp_builder(v):
    cylinder("base", (0, 0, 0.14), 0.28, 0.28, "stone", 8)
    cylinder("post", (0, 0, 1.65), 0.10, 3.0, "metal", 8)
    cube("lantern housing", (0, 0, 3.20), (0.58, 0.58, 0.62), "navy", 0.06)
    cube("lantern glass", (0, -0.30, 3.20), (0.37, 0.035, 0.38), "gold")
    cube("lantern glass side", (0.30, 0, 3.20), (0.035, 0.37, 0.38), "gold")
    cylinder("cap", (0, 0, 3.58), 0.40, 0.15, "metal", 8, 0.27)
    cylinder("finial", (0, 0, 3.72), 0.08, 0.18, "metal", 8, 0.02)


# 新建干净场景，保存可编辑源文件。
bpy.ops.object.select_all(action="SELECT")
bpy.ops.object.delete(use_global=False)
for d in list(bpy.data.collections):
    if d.name != "Collection":
        bpy.data.collections.remove(d)
scene = bpy.context.scene
scene.render.engine = "BLENDER_EEVEE"
assets = []
project = "Created for CoastalDrive VI asset kit; original Blender geometry and materials."
license_project = "Project-generated; no external source assets."
build_asset(
    "pine_tall_a",
    "Five broad overlapping pine whorls with an exposed lower trunk, approximately 7.5 m tall.",
    project,
    "Project-generated geometry using CoastalDrive coastal palette.",
    7.5,
    builder=pine_builder,
    variant=0,
)
build_asset(
    "pine_tall_b",
    "Wind-shaped variant with five broad overlapping pine whorls, approximately 8.3 m tall.",
    project,
    "Project-generated geometry using CoastalDrive coastal palette.",
    8.3,
    builder=pine_builder,
    variant=1,
)
build_asset(
    "bush_round_a",
    "Irregular leafy roadside shrub variant, approximately 1.1 m tall.",
    project,
    license_project,
    1.1,
    builder=bush_builder,
    variant=0,
)
build_asset(
    "bush_round_b",
    "Asymmetric leafy roadside shrub variant, approximately 1.25 m tall.",
    project,
    license_project,
    1.25,
    builder=bush_builder,
    variant=1,
)
build_asset(
    "rock_coastal_a",
    "Large stratified asymmetric limestone boulder, approximately 1.8 m tall.",
    project,
    license_project,
    1.8,
    builder=rock_builder,
    variant=0,
)
build_asset(
    "rock_coastal_b",
    "Broad broken limestone boulder variant, approximately 1.65 m tall.",
    project,
    license_project,
    1.65,
    builder=rock_builder,
    variant=1,
)
build_asset(
    "flowers_coastal_a",
    "Four-stem coastal flower clump, approximately 0.8 m tall.",
    project,
    license_project,
    0.8,
    builder=flowers_builder,
)
build_asset(
    "cliff_coastal_a",
    "Single tapered limestone mass with subtle strata and a flat grassy cap, approximately 3.4 m tall.",
    project,
    license_project,
    3.4,
    builder=cliff_builder,
)
build_asset(
    "lighthouse_coastal_a",
    "Tapered 14 m coastal lighthouse with lantern glazing, cornices and gallery rail.",
    project,
    license_project,
    14.0,
    builder=lighthouse_builder,
)
build_asset(
    "coastal_house_a",
    "Limewashed 5.6 m coastal cottage with tile roof, shutters, porch and chimney.",
    project,
    license_project,
    5.5,
    builder=house_builder,
)
build_asset(
    "road_chevron_sign_a",
    "Reflective coastal route chevron sign, approximately 2.1 m tall.",
    project,
    license_project,
    2.1,
    builder=sign_builder,
)
build_asset(
    "coastal_lamp_a",
    "Coastal street lamp with glass lantern, approximately 3.8 m tall.",
    project,
    license_project,
    3.8,
    builder=lamp_builder,
)

# 将独立资产排布在编辑场景中，并按名称分组。
scene.render.resolution_x = 1600
scene.render.resolution_y = 900
scene.render.resolution_percentage = 100
scene.world.color = (0.35, 0.47, 0.55)
for i, a in enumerate(assets):
    obj = a["object"]
    obj.location = ((i % 4) * 8.0, (i // 4) * 10.0, 0)
    obj["source_note"] = a["source"]
    obj["license_note"] = a["license"]
    # 在大纲视图和自定义属性中记录资产信息。
    obj["origin"] = "Ground center (Blender Z=0)"
    obj["target_height_m"] = a["target_height_m"]

# 导出前保存可编辑场景。
bpy.ops.wm.save_as_mainfile(filepath=str(BLEND))
manifest = {
    "kit": "CoastalDrive Coastal Environment Kit",
    "version": 1,
    "blender": "5.2.2",
    "units": "meters; Blender Z-up source; GLB exported through Blender glTF Y-up conversion",
    "asset_count": len(assets),
    "triangle_budget": 30000,
    "assets": [],
}
for i, a in enumerate(assets):
    obj = a["object"]
    original = obj.location.copy()
    obj.location = (0, 0, 0)
    bpy.ops.object.select_all(action="DESELECT")
    obj.select_set(True)
    bpy.context.view_layer.objects.active = obj
    path = OUT / (a["name"] + ".glb")
    bpy.ops.export_scene.gltf(
        filepath=str(path),
        export_format="GLB",
        use_selection=True,
        export_apply=True,
        export_yup=True,
    )
    obj.location = original
    bpy.context.view_layer.update()
    coords = [obj.matrix_world @ Vector(c) for c in obj.bound_box]
    lo = Vector((min(v.x for v in coords), min(v.y for v in coords), min(v.z for v in coords)))
    hi = Vector((max(v.x for v in coords), max(v.y for v in coords), max(v.z for v in coords)))
    tri = sum(max(0, len(p.vertices) - 2) for p in obj.data.polygons)
    manifest["assets"].append(
        {
            "name": a["name"],
            "file": "models/" + path.name,
            "description": a["description"],
            "source": a["source"],
            "license": a["license"],
            "origin": "ground-centered, Z=0 in editable Blender source",
            "bounds_m": {
                "x": round(hi.x - lo.x, 3),
                "y": round(hi.y - lo.y, 3),
                "z": round(hi.z - lo.z, 3),
            },
            "triangles": tri,
            "vertices": len(obj.data.vertices),
        }
    )
manifest["total_triangles"] = sum(a["triangles"] for a in manifest["assets"])
MANIFEST.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
print("KIT_EXPORT_COMPLETE", len(assets), manifest["total_triangles"], BLEND)
