"""制作三款原创轻量交通车；Blender 源文件与 GLB 同步导出。"""

import json
import math
import struct
from pathlib import Path

import bpy

ROOT = Path(__file__).resolve().parents[2]
ART = ROOT / "art/vehicles"
OUT = ROOT / "assets/game/vehicles"
SPECS = {
    "compact": {"length": 3.58, "width": 1.70, "hood": 0.83, "roof": 1.36,
                "deck": 0.35, "shoulder": 0.48},
    "sedan": {"length": 4.17, "width": 1.83, "hood": 1.14, "roof": 1.20,
              "deck": 0.68, "shoulder": 0.46},
    "wagon": {"length": 4.12, "width": 1.90, "hood": 0.91, "roof": 1.49,
              "deck": 0.39, "shoulder": 0.51},
}
WHEELS = ("wheel-front-left", "wheel-front-right", "wheel-back-left", "wheel-back-right")


def material(name, color, roughness, metallic=0):
    mat = bpy.data.materials.new(name)
    mat.diffuse_color = (*color, 1)
    mat.use_nodes = True
    shader = mat.node_tree.nodes.get("Principled BSDF")
    shader.inputs["Base Color"].default_value = (*color, 1)
    shader.inputs["Roughness"].default_value = roughness
    shader.inputs["Metallic"].default_value = metallic
    return mat


def empty(name, parent=None, location=(0, 0, 0)):
    obj = bpy.data.objects.new(name, None)
    bpy.context.collection.objects.link(obj)
    obj.parent = parent
    obj.location = location
    return obj


def mesh(name, vertices, faces, mat, parent):
    data = bpy.data.meshes.new(name)
    data.from_pydata(vertices, [], faces)
    data.update()
    obj = bpy.data.objects.new(name, data)
    bpy.context.collection.objects.link(obj)
    obj.parent = parent
    data.materials.append(mat)
    return obj


def box(name, centre, size, mat, parent, bevel=0):
    bpy.ops.mesh.primitive_cube_add(size=1, location=centre)
    obj = bpy.context.object
    obj.name = name
    obj.dimensions = size
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    obj.parent = parent
    obj.data.materials.append(mat)
    if bevel:
        mod = obj.modifiers.new("Soft edges", "BEVEL")
        mod.width = bevel
        mod.segments = 2
        bpy.ops.object.modifier_apply(modifier=mod.name)
        normal = obj.modifiers.new("Panel normals", "WEIGHTED_NORMAL")
        bpy.ops.object.modifier_apply(modifier=normal.name)
    return obj


def pane(name, points, mat, parent):
    return mesh(name, points, [(0, 1, 2, 3), (3, 2, 1, 0)], mat, parent)


def wheel(name, parent, x, y, rubber, metal, dark):
    pivot = empty(name, parent, (x, y, -0.12))
    bpy.ops.mesh.primitive_cylinder_add(vertices=24, radius=0.33, depth=0.12,
                                        location=(0, 0, 0), rotation=(0, math.pi / 2, 0))
    tire = bpy.context.object
    tire.name = "tire"
    tire.parent = pivot
    tire.data.materials.append(rubber)
    for side in (-1, 1):
        bpy.ops.mesh.primitive_cylinder_add(vertices=16, radius=0.21, depth=0.006,
                                            location=(side * 0.063, 0, 0), rotation=(0, math.pi / 2, 0))
        rim = bpy.context.object
        rim.name = "wheel-face"
        rim.parent = pivot
        rim.data.materials.append(metal)
        bpy.ops.mesh.primitive_cylinder_add(vertices=12, radius=0.11, depth=0.009,
                                            location=(side * 0.068, 0, 0), rotation=(0, math.pi / 2, 0))
        hub = bpy.context.object
        hub.name = "wheel-hub"
        hub.parent = pivot
        hub.data.materials.append(dark)


def build(kind, spec):
    bpy.ops.object.select_all(action="SELECT")
    bpy.ops.object.delete(use_global=False)
    for mat in list(bpy.data.materials):
        bpy.data.materials.remove(mat)
    bpy.context.scene.unit_settings.system = "METRIC"
    bpy.context.scene.unit_settings.scale_length = 1

    paint_mat = material("Body Paint", (0.38, 0.12, 0.025), 0.36)
    glass = material("Blue Grey Glass", (0.006, 0.012, 0.019), 0.17)
    trim = material("Satin Black Plastic", (0.019, 0.025, 0.029), 0.65)
    rubber = material("Tire Rubber", (0.009, 0.011, 0.013), 0.94)
    metal = material("Brushed Wheel Metal", (0.48, 0.51, 0.54), 0.18, 0.90)
    head = material("Head Light", (0.53, 0.61, 0.60), 0.22)
    tail = material("Tail Light", (0.48, 0.012, 0.014), 0.25)
    amber = material("Amber Lens", (0.74, 0.29, 0.018), 0.24)

    root = empty(f"traffic-{kind}-v1")
    paint = empty("paint", root)
    length, width = spec["length"], spec["width"]
    front, rear = length / 2, -length / 2
    shoulder, roof = spec["shoulder"], spec["roof"]
    half = width / 2
    # 低面数连续车壳：侧边随轮心抬高，真实留出四个圆弧轮拱。
    stations = sorted(set([rear + index * length / 48 for index in range(49)]
                          + [hub + offset for hub in (-1.1, 1.1)
                             for offset in (-0.36, -0.30, 0, 0.30, 0.36)]))
    vertices = []
    ring_size = 11
    for y in stations:
        arch = max((-0.12 + math.sqrt(max(0, 0.36**2 - (y - hub)**2))
                    for hub in (-1.1, 1.1) if abs(y - hub) < 0.36), default=-0.25)
        side_low = max(-0.25, arch)
        taper = 1 - 0.055 * (abs(y) / (length / 2))**5
        w = half * taper
        top = shoulder + 0.12 - 0.035 * (abs(y) / (length / 2))**4
        section = [(-w * 0.76, top), (0, top + 0.018), (w * 0.76, top),
                   (w, top - 0.075), (w, side_low + 0.05),
                   (w * 0.88, side_low), (w * 0.60, -0.27),
                   (-w * 0.60, -0.27), (-w * 0.88, side_low),
                   (-w, side_low + 0.05), (-w, top - 0.075)]
        vertices.extend((x, y, z) for x, z in section)
    faces = [tuple(reversed(range(ring_size)))]
    for index in range(len(stations) - 1):
        faces.extend((index * ring_size + j, index * ring_size + (j + 1) % ring_size,
                      (index + 1) * ring_size + (j + 1) % ring_size,
                      (index + 1) * ring_size + j) for j in range(ring_size))
    faces.append(tuple((len(stations) - 1) * ring_size + j for j in range(ring_size)))
    body_shell = mesh("sculpted body and wheel arches", vertices, faces, paint_mat, paint)
    normals = body_shell.modifiers.new("Body panel normals", "WEIGHTED_NORMAL")
    bpy.context.view_layer.objects.active = body_shell
    bpy.ops.object.modifier_apply(modifier=normals.name)
    for side in (-1, 1):
        box("shoulder crease", (side * (half + 0.002), 0, shoulder + 0.055),
            (0.008, length - 0.24, 0.012), metal, root)
    box("lower undertray", (0, 0, -0.29), (width - 0.50, length - 0.16, 0.06), trim, root)

    cabin_front = front - spec["hood"]
    cabin_rear = rear + spec["deck"]
    roof_front = cabin_front - 0.31
    roof_rear = cabin_rear + (0.27 if kind != "wagon" else 0.11)
    top_half = half * (0.70 if kind == "compact" else 0.76)
    bottom_z = shoulder + 0.12
    top_z = roof
    rings = []
    for y, z, w in ((cabin_rear, bottom_z, half * 0.87),
                    (roof_rear, top_z, top_half),
                    (roof_front, top_z, top_half),
                    (cabin_front, bottom_z, half * 0.87)):
        rings.extend(((-w, y, z), (w, y, z)))
    faces = [(0, 1, 3, 2), (2, 3, 5, 4), (4, 5, 7, 6),
             (0, 2, 4, 6), (1, 7, 5, 3), (0, 6, 7, 1)]
    mesh("solid roof and pillars", rings, faces, paint_mat, paint)
    inset = 0.035
    pane("windshield", [(-top_half + inset, roof_front + 0.018, top_z - inset),
                        (top_half - inset, roof_front + 0.018, top_z - inset),
                        (half * 0.84, cabin_front + 0.018, bottom_z + inset),
                        (-half * 0.84, cabin_front + 0.018, bottom_z + inset)], glass, root)
    pane("rear glass", [(-half * 0.84, cabin_rear - 0.018, bottom_z + inset),
                       (half * 0.84, cabin_rear - 0.018, bottom_z + inset),
                       (top_half - inset, roof_rear - 0.018, top_z - inset),
                       (-top_half + inset, roof_rear - 0.018, top_z - inset)], glass, root)
    for side in (-1, 1):
        # 斜边玻璃与独立 B 柱让车窗在常规驾驶距离仍可读。
        x = side * (half * 0.87 + top_half) / 2
        pane("side glass front", [(side * half * 0.89, cabin_front - 0.035, bottom_z + 0.055),
                                  (side * (top_half + 0.014), roof_front - 0.035, top_z - 0.055),
                                  (side * (top_half + 0.014), -0.02, top_z - 0.055),
                                  (side * half * 0.89, -0.02, bottom_z + 0.055)], glass, root)
        pane("side glass rear", [(side * half * 0.89, -0.09, bottom_z + 0.055),
                                 (side * (top_half + 0.014), -0.09, top_z - 0.055),
                                 (side * (top_half + 0.014), roof_rear + 0.035, top_z - 0.055),
                                 (side * half * 0.89, cabin_rear + 0.035, bottom_z + 0.055)], glass, root)
        box("B pillar", (x, -0.055, (bottom_z + top_z) / 2),
            (0.035, 0.045, top_z - bottom_z), trim, root)
        box("glass sill", (side * half * 0.85, (cabin_front + cabin_rear) / 2,
                            bottom_z + 0.045),
            (0.020, cabin_front - cabin_rear - 0.06, 0.023), trim, root)
        box("door shut line", (side * (half + 0.009), -0.08, shoulder - 0.09),
            (0.012, 0.016, 0.26), trim, root)
        box("door handle", (side * (half + 0.007), 0.03, shoulder + 0.11),
            (0.018, 0.16, 0.035), metal, root, 0.006)
        box("mirror stalk", (side * (half + 0.015), cabin_front + 0.10, shoulder + 0.19),
            (0.08, 0.09, 0.085), trim, root, 0.018)
        box("headlamp", (side * half * 0.68, front + 0.007, shoulder - 0.03),
            (0.36, 0.018, 0.15), head, root, 0.018)
        box("taillamp", (side * half * 0.67, rear - 0.007, shoulder - 0.02),
            (0.40, 0.018, 0.16), tail, root, 0.018)
        box("indicator", (side * half * 0.91, front + 0.008, shoulder - 0.13),
            (0.095, 0.015, 0.07), amber, root)
        box("foglamp", (side * half * 0.60, front + 0.035, -0.12),
            (0.13, 0.014, 0.065), head, root, 0.008)
        box("hood crease", (side * half * 0.47, (front + cabin_front) / 2,
                            shoulder + 0.126),
            (0.015, spec["hood"] - 0.16, 0.014), metal, root)
    box("front grille", (0, front + 0.013, shoulder - 0.10),
        (width * 0.39, 0.025, 0.15), trim, root, 0.015)
    box("grille upper bar", (0, front + 0.031, shoulder - 0.055),
        (width * 0.34, 0.012, 0.014), metal, root)
    box("front licence", (0, front + 0.041, -0.12), (0.32, 0.012, 0.10), metal, root)
    box("rear licence", (0, rear - 0.041, shoulder - 0.10),
        (0.34, 0.012, 0.11), metal, root)
    box("rear dark recess", (0, rear - 0.032, shoulder - 0.115),
        (0.43, 0.012, 0.14), trim, root)
    for y in (rear - 0.026, front + 0.026):
        box("bumper", (0, y, -0.12), (width - 0.11, 0.065, 0.11), trim, root, 0.025)
    if kind == "wagon":
        for side in (-1, 1):
            box("roof rail", (side * top_half * 0.79, (roof_front + roof_rear) / 2, roof + 0.035),
                (0.042, roof_front - roof_rear + 0.16, 0.07), trim, root, 0.012)
        box("tailgate handle", (0, rear - 0.020, shoulder + 0.18),
            (0.20, 0.018, 0.034), metal, root)
    elif kind == "compact":
        box("hatch spoiler", (0, roof_rear - 0.08, roof + 0.025),
            (top_half * 2 + 0.05, 0.20, 0.05), trim, root, 0.018)
    else:
        box("sedan trunk trim", (0, rear - 0.016, shoulder + 0.10),
            (width * 0.36, 0.018, 0.025), metal, root)
    for name, y, side in zip(WHEELS, (1.1, 1.1, -1.1, -1.1), (-1, 1, -1, 1)):
        wheel(name, root, side * 0.84, y, rubber, metal, trim)

    bpy.context.scene.world.color = (0.15, 0.19, 0.24)
    bpy.ops.wm.save_as_mainfile(filepath=str(ART / f"traffic_{kind}_v1.blend"))
    path = OUT / f"traffic_{kind}_v1.glb"
    bpy.ops.export_scene.gltf(filepath=str(path), export_format="GLB", export_yup=True,
                              export_apply=True)
    data = path.read_bytes()
    length = struct.unpack_from("<I", data, 12)[0]
    gltf = json.loads(data[20:20 + length])
    triangles = sum(gltf["accessors"][p["indices"]]["count"] // 3
                    for model in gltf["meshes"] for p in model["primitives"])
    return {"model": kind, "triangles": triangles, "budget": 8500,
            "body_length_m": spec["length"], "body_width_m": spec["width"],
            "wheel_centres_m": [[side * 0.84, y, -0.12]
                                for y in (1.1, -1.1) for side in (-1, 1)]}


for folder in (ART, OUT):
    folder.mkdir(parents=True, exist_ok=True)
results = [build(kind, spec) for kind, spec in SPECS.items()]
(OUT / "traffic-family-manifest.json").write_text(
    json.dumps({"source": "original editable CoastalDrive Blender geometry",
                "units": "metres; +Y forward; Z up", "blender": bpy.app.version_string,
                "vehicles": results}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
)
print("TRAFFIC_FAMILY_EXPORTED", results)
