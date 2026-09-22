import json
import sys
from pathlib import Path

import bpy

project_root = Path(__file__).resolve().parents[1]
source_model = project_root / "assets" / "game" / "player-car.glb"
roundtrip_model = project_root / "builds" / "phase0-blender-roundtrip.glb"
report_path = project_root / "logs" / "phase0-blender.json"

bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.gltf(filepath=str(source_model))

objects = list(bpy.context.scene.objects)
meshes = [obj for obj in objects if obj.type == "MESH"]
materials = {material.name for obj in meshes for material in obj.data.materials if material}

roundtrip_model.parent.mkdir(parents=True, exist_ok=True)
bpy.ops.export_scene.gltf(filepath=str(roundtrip_model), export_format="GLB")

report = {
    "blender_version": bpy.app.version_string,
    "source_model": str(source_model),
    "object_count": len(objects),
    "mesh_count": len(meshes),
    "material_count": len(materials),
    "roundtrip_model": str(roundtrip_model),
    "roundtrip_bytes": roundtrip_model.stat().st_size,
    "passed": bool(meshes) and roundtrip_model.exists() and roundtrip_model.stat().st_size > 0,
}
report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
print(json.dumps(report, ensure_ascii=False, indent=2))
sys.exit(0 if report["passed"] else 1)

