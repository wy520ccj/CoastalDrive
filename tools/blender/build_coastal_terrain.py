"""将已冻结的地貌顶点数据制成可编辑 Blender 与运行 GLB。"""

import json
import sys
from pathlib import Path

import bpy

ROOT = Path(__file__).resolve().parents[2]
data = json.loads(Path(sys.argv[sys.argv.index("--") + 1]).read_text(encoding="utf-8"))
bpy.ops.object.select_all(action="SELECT")
bpy.ops.object.delete(use_global=False)
for item in data:
    mesh = bpy.data.meshes.new(item["name"])
    mesh.from_pydata(item["vertices"], [], item["faces"])
    mesh.update()
    color = mesh.color_attributes.new(name="Color", type="FLOAT_COLOR", domain="POINT")
    for v, c in zip(color.data, item["colors"]):
        v.color = c
    uv = mesh.uv_layers.new(name="UVMap")
    for loop in mesh.loops:
        p = mesh.vertices[loop.vertex_index].co
        uv.data[loop.index].uv = (p.x / 2.5, p.y / 2.5)
    for poly in mesh.polygons:
        poly.use_smooth = item["name"] == "inland"
    obj = bpy.data.objects.new(item["name"], mesh)
    bpy.context.collection.objects.link(obj)
    mat = bpy.data.materials.new(item["name"])
    mat.use_nodes = True
    mat.use_backface_culling = item["name"] != "ground-cover"
    shader = mat.node_tree.nodes.get("Principled BSDF")
    shader.inputs["Base Color"].default_value = (1, 1, 1, 1)
    shader.inputs["Roughness"].default_value = 0.95
    vc = mat.node_tree.nodes.new("ShaderNodeVertexColor")
    vc.layer_name = "Color"
    mat.node_tree.links.new(vc.outputs["Color"], shader.inputs["Base Color"])
    obj.data.materials.append(mat)
bpy.ops.wm.save_as_mainfile(filepath=str(ROOT / "art/coastal/coastal_terrain.blend"))
bpy.ops.export_scene.gltf(
    filepath=str(ROOT / "assets/game/environment/terrain/coastal-terrain.glb"),
    export_format="GLB",
    export_yup=True,
)
