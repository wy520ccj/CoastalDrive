"""制作原创掀背、敞篷、GT和车库；只输出本任务专用新资产。"""

import hashlib
import json
import math
from pathlib import Path

import bmesh
import bpy

ROOT = Path(__file__).resolve().parents[2]
ART = ROOT/'art/vehicles'
OUT = ROOT/'assets/game/vehicles'


def material(name, color, roughness=.4, metal=0):
    mat = bpy.data.materials.new(name)
    mat.diffuse_color = (*color, 1)
    mat.use_nodes = True
    shader = mat.node_tree.nodes['Principled BSDF']
    shader.inputs['Base Color'].default_value = (*color, 1)
    shader.inputs['Roughness'].default_value = roughness
    shader.inputs['Metallic'].default_value = metal
    return mat


def empty(name, parent=None, position=(0, 0, 0)):
    node = bpy.data.objects.new(name, None)
    bpy.context.collection.objects.link(node)
    node.parent, node.location = parent, position
    return node


def box(name, pos, size, mat, parent, bevel=.025):
    bpy.ops.mesh.primitive_cube_add(size=1, location=pos)
    obj = bpy.context.object
    obj.name, obj.parent, obj.dimensions = name, parent, size
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    obj.data.materials.append(mat)
    if bevel:
        mod = obj.modifiers.new('Panel radius', 'BEVEL')
        mod.width, mod.segments = bevel, 2
        bpy.ops.object.modifier_apply(modifier=mod.name)
        mod = obj.modifiers.new('Panel normals', 'WEIGHTED_NORMAL')
        bpy.ops.object.modifier_apply(modifier=mod.name)
    obj.select_set(False)
    return obj


def mesh(name, points, faces, mat, parent):
    data = bpy.data.meshes.new(name)
    data.from_pydata(points, [], faces)
    data.update()
    edit = bmesh.new()
    edit.from_mesh(data)
    bmesh.ops.recalc_face_normals(edit, faces=list(edit.faces))
    edit.to_mesh(data)
    edit.free()
    obj = bpy.data.objects.new(name, data)
    bpy.context.collection.objects.link(obj)
    obj.parent = parent
    data.materials.append(mat)
    return obj


def reset():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    bpy.context.scene.unit_settings.system = 'METRIC'


def export(name):
    bpy.ops.wm.save_as_mainfile(filepath=str(ART/(name+'.blend')))
    path = OUT/(name+'.glb')
    bpy.ops.export_scene.gltf(filepath=str(path), export_format='GLB', export_yup=True, export_apply=True)
    return {'asset': str(path.relative_to(ROOT)).replace('\\', '/'),
            'sha256': hashlib.sha256(path.read_bytes()).hexdigest(),
            'source': str((ART/(name+'.blend')).relative_to(ROOT)).replace('\\', '/')}


def car(kind, length, width, roof, axle):
    reset()
    root = empty('coastal-'+kind)
    paint = empty('paint', root)
    body = material('Body Paint', (.05, .34, .55), .27, .3)
    glass = material('Deep blue glass', (.012, .031, .045), .16, .25)
    trim = material('Graphite trim', (.018, .024, .03), .52)
    rubber = material('Tire rubber', (.009, .011, .015), .85)
    alloy = material('Machined alloy', (.45, .5, .55), .22, .82)
    head = material('LED white', (.82, .94, 1.), .18)
    tail = material('Tail red', (.65, .015, .025), .22)
    seat = material('Leather', (.19, .075, .035), .65)
    half, front, rear = width/2, length/2, -length/2
    shoulder = .73 if kind == 'roadster' else .82
    sections = [(rear, half*.87, .30, shoulder-.11), (rear+.20, half*.97, .23, shoulder-.02),
                (-.7, half, .19, shoulder+.015), (.65, half, .19, shoulder+.01),
                (front-.25, half*.96, .23, shoulder-.07), (front, half*.87, .31, shoulder-.16)]
    points = [(x, y, z) for y, w, low, top in sections for x, z in
              ((-w, low), (w, low), (w, top), (-w, top))]
    faces = [(3, 2, 1, 0)]
    for index in range(len(sections)-1):
        for side in range(4):
            a, b = index*4+side, index*4+(side+1)%4
            faces.append((a, b, b+4, a+4))
    faces.append(tuple(range(len(points)-4, len(points))))
    shell = mesh('sculpted-body', points, faces, body, paint)
    # 实际车轮开口贯穿左右侧板；不通过外贴黑圆伪装轮拱。
    for y in (-axle/2, axle/2):
        bpy.ops.mesh.primitive_cylinder_add(vertices=48, radius=.355, depth=width+.5,
            location=(0, y, .30), rotation=(0, math.pi/2, 0))
        cutter = bpy.context.object
        bpy.context.view_layer.objects.active = shell
        mod = shell.modifiers.new('Wheel arch opening', 'BOOLEAN')
        mod.operation, mod.object = 'DIFFERENCE', cutter
        bpy.ops.object.modifier_apply(modifier=mod.name)
        bpy.data.objects.remove(cutter, do_unlink=True)
    bpy.context.view_layer.objects.active = shell
    mod = shell.modifiers.new('Rounded body panels', 'BEVEL')
    mod.width, mod.segments = .035, 3
    bpy.ops.object.modifier_apply(modifier=mod.name)
    mod = shell.modifiers.new('Body panel normals', 'WEIGHTED_NORMAL')
    bpy.ops.object.modifier_apply(modifier=mod.name)
    for side in (-1, 1):
        for y in (-axle/2, axle/2):
            vertices = [(side*(half+.005), y+math.cos(i*math.pi/24)*radius,
                         .30+math.sin(i*math.pi/24)*radius)
                        for i in range(25) for radius in (.355, .38)]
            mesh('wheel arch trim', vertices, [(i*2, i*2+1, i*2+3, i*2+2) for i in range(24)], trim, root)
    if kind == 'hatch':
        back, top_back, top_front, windshield = rear+.13, -.93, .37, .94
    elif kind == 'gt':
        back, top_back, top_front, windshield = -1.3, -.70, .20, 1.10
    else:
        back, top_back, top_front, windshield = -.80, -.46, .24, .85
    topwidth = half*.76
    if kind != 'roadster':
        cabin = [(-half*.91, back, shoulder), (half*.91, back, shoulder),
                 (-topwidth, top_back, roof), (topwidth, top_back, roof),
                 (-topwidth, top_front, roof), (topwidth, top_front, roof),
                 (-half*.90, windshield, shoulder), (half*.90, windshield, shoulder)]
        cabin_obj = mesh('cabin-paint', cabin, [(0, 2, 3, 1), (2, 4, 5, 3), (4, 6, 7, 5),
                                   (0, 6, 4, 2), (1, 3, 5, 7), (0, 1, 7, 6)], body, paint)
        bpy.context.view_layer.objects.active = cabin_obj
        mod = cabin_obj.modifiers.new('Roof radius', 'BEVEL')
        mod.width, mod.segments = .045, 3
        bpy.ops.object.modifier_apply(modifier=mod.name)
        for side in (-1, 1):
            mesh('side-window', [(side*(half*.913), back+.12, shoulder+.055),
                (side*(topwidth+.012), top_back+.08, roof-.06),
                (side*(topwidth+.012), top_front-.05, roof-.06),
                (side*(half*.902), windshield-.14, shoulder+.055)], [(0, 1, 2, 3), (3, 2, 1, 0)], glass, root)
            pillar = box('B pillar', (side*half*.855, -.30, (roof+shoulder)/2),
                         (.055, .055, roof-shoulder-.06), trim, root, .008)
            pillar.rotation_euler[1] = side*.18
        for name, y1, y2 in [('windscreen', top_front, windshield), ('rear-glass', top_back, back)]:
            mesh(name, [(-topwidth+.045, y1+.005, roof-.05), (topwidth-.045, y1+.005, roof-.05),
                 (half*.83, y2, shoulder+.055), (-half*.83, y2, shoulder+.055)],
                 [(0, 1, 2, 3), (3, 2, 1, 0)], glass, root)
    else:
        box('open cockpit', (0, -.16, .755), (width*.72, 1.12, .04), trim, root)
        for side in (-1, 1):
            box('seat back', (side*.36, -.48, .76), (.48, .19, .46), seat, root, .07)
            box('head rest', (side*.36, -.48, 1.01), (.26, .17, .20), trim, root, .05)
            bpy.ops.mesh.primitive_torus_add(major_radius=.16, minor_radius=.025,
                major_segments=24, minor_segments=8, location=(side*.36, -.75, .95),
                rotation=(math.pi/2, 0, 0))
            hoop = bpy.context.object
            hoop.name, hoop.parent = 'roll hoop', root
            hoop.data.materials.append(alloy)
            post = box('windshield pillar', (side*.71, .59, .89), (.055, .055, .61), body, paint, .012)
            post.rotation_euler[0] = .43
        mesh('windscreen', [(-.69, .73, .61), (.69, .73, .61), (.63, .48, 1.17), (-.63, .48, 1.17)],
             [(0, 1, 2, 3), (3, 2, 1, 0)], glass, root)
        box('windshield rail', (0, .48, 1.17), (1.35, .05, .055), body, paint)
        box('rear deck', (0, -1.26, .74), (width*.88, .68, .08), body, paint)
    for side in (-1, 1):
        box('door handle', (side*half*1.005, -.34, shoulder-.10), (.018, .19, .035), alloy, root, .009)
        box('side skirt', (side*half, 0, .19), (.035, length*.56, .09), trim, root)
        box('door shut line', (side*half*1.002, -.69, shoulder-.22), (.009, .009, .35), trim, root, .002)
        box('mirror', (side*(half+.10), .65, .68), (.19, .22, .10), body, paint, .035)
        box('head lamp', (side*width*.30, front+.012, shoulder-.24), (width*.23, .035, .085), head, root, .025)
        box('tail lamp', (side*width*.30, rear-.015, shoulder-.16), (width*.24, .035, .065), tail, root, .015)
    for y in (front+.016, rear-.016):
        box('lower bumper', (0, y, .33), (width*.84, .045, .10), trim, root)
        box('licence plate', (0, y*1.015, .46), (.35, .018, .08), alloy, root, .01)
    box('grille', (0, front+.04, .48), (width*.4, .03, .16), trim, root)
    if kind == 'hatch':
        box('roof spoiler', (0, top_back-.07, roof+.025), (width*.84, .24, .055), trim, root)
    elif kind == 'gt':
        box('GT lip', (0, rear+.14, .57), (width*.84, .18, .055), body, paint)
    for name, y, side in zip(('wheel-front-left', 'wheel-front-right', 'wheel-back-left', 'wheel-back-right'),
                             (axle/2, axle/2, -axle/2, -axle/2), (-1, 1, -1, 1)):
        pivot = empty(name, root, (side*half*.86, y, .30))
        bpy.ops.mesh.primitive_cylinder_add(vertices=40, radius=.30, depth=.20,
            rotation=(0, math.pi/2, 0))
        tire = bpy.context.object
        tire.name, tire.parent = 'tire', pivot
        tire.data.materials.append(rubber)
        for edge in (-1, 1):
            bpy.ops.mesh.primitive_cylinder_add(vertices=32, radius=.225, depth=.012,
                location=(edge*.106, 0, 0), rotation=(0, math.pi/2, 0))
            disc = bpy.context.object
            disc.name, disc.parent = 'rim', pivot
            disc.data.materials.append(trim)
            for spoke in range(5):
                angle = spoke*math.tau/5
                obj = box('alloy spoke', (edge*.117, math.sin(angle)*.105, math.cos(angle)*.105),
                          (.012, .045, .21), alloy, pivot, .009)
                obj.rotation_euler[0] = -angle
    return export('coastal_'+kind)


def garage():
    reset()
    root = empty('coastal-festival-garage')
    white = material('Warm plaster', (.78, .79, .74), .72)
    floor = material('Pale terrazzo', (.55, .60, .60), .34)
    blue = material('Deep coastal blue', (.025, .16, .23), .45)
    wood = material('Natural oak', (.40, .24, .12), .68)
    light = material('Skylight white', (.87, .96, 1.), .7)
    orange = material('Coral', (.85, .15, .05), .5)
    black = material('Tool graphite', (.025, .038, .05), .55)
    green = material('Plant', (.08, .23, .13), .8)
    box('floor', (0, 0, -.125), (30, 32, .20), floor, root, 0)
    box('rear wall', (0, -7, 3), (20, .25, 6), white, root, 0)
    box('side wall', (-9, 0, 3), (.25, 14, 6), white, root, 0)
    for x in range(-8, 10, 4):
        box('blue column', (x, -6.7, 2.9), (.20, .4, 5.8), blue, root)
        box('roof beam', (x, -.2, 5.8), (.15, 13, .18), white, root)
    for y in (-4, 0, 4):
        box('sky panel', (-8.85, y, 3.2), (.03, 3.2, 3.5), light, root, 0)
        box('window sill', (-8.7, y, 1.37), (.3, 3.4, .09), blue, root)
    for x in range(28):
        box('oak slat', (-3.6+x*.18, -6.80, 2.6), (.10, .16, 3.4), wood, root, .01)
    box('tool bench', (5.4, -5.7, .53), (3.7, .8, 1.06), blue, root)
    box('wood worktop', (5.4, -5.7, 1.10), (3.85, .9, .12), wood, root)
    for z in (.27, .53, .79):
        box('drawer line', (5.4, -5.27, z), (3.4, .025, .018), black, root, 0)
    box('coral rolling tool chest', (-5.6, -4.6, .5), (1.3, .7, 1.), orange, root)
    for x in (-6.9, 7.7):
        box('planter', (x, -5.1, .35), (.6, .6, .7), white, root)
        for i in range(5):
            leaf = box('plant leaf', (x+(i-2)*.10, -5.1, 1.02+abs(i-2)*.07), (.18, .25, 1.0), green, root, .07)
            leaf.rotation_euler[1] = (i-2)*.18
    for x in (-2.2, 2.2):
        box('parking bay line', (x, 0, .005), (.035, 6., .006), white, root, 0)
    bpy.ops.object.text_add(location=(-2.8, -6.63, 3.0), rotation=(math.pi/2, 0, 0))
    text = bpy.context.object
    text.name, text.parent = 'COASTAL workshop sign', root
    text.data.body, text.data.size, text.data.extrude = 'COASTAL', .82, .012
    text.data.materials.append(white)
    bpy.ops.object.convert(target='MESH')
    return export('coastal_garage')


rows = [car('hatch', 3.86, 1.80, 1.38, 2.48),
        car('roadster', 3.96, 1.80, 1.17, 2.34), car('gt', 4.56, 1.98, 1.27, 2.75), garage()]
(OUT/'coastal-garage-manifest.json').write_text(json.dumps({
    'source': 'Original CoastalDrive geometry; no third-party mesh or texture',
    'units': 'metres; +Y forward; Z up', 'blender': bpy.app.version_string,
    'generator': 'tools/blender/build_coastal_garage.py', 'assets': rows}, indent=2), encoding='utf-8')
