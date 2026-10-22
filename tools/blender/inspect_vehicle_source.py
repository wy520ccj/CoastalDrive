"""离线检查单个候选Blender场景；不执行来源文件的自动脚本。"""

import json
import sys
from pathlib import Path

import bpy

source = Path(sys.argv[sys.argv.index('--')+1]).resolve()
bpy.ops.wm.open_mainfile(filepath=str(source), load_ui=False, use_scripts=False)
objects = [{'name': obj.name, 'type': obj.type, 'parent': obj.parent.name if obj.parent else None,
            'dimensions': list(obj.dimensions), 'location': list(obj.matrix_world.translation),
            'materials': [slot.material.name if slot.material else None for slot in obj.material_slots]}
           for obj in bpy.context.scene.objects]
materials = []
for material in bpy.data.materials:
    nodes = [] if material.node_tree is None else [
        {'type': node.type, 'name': node.name,
         'image': node.image.name if node.type == 'TEX_IMAGE' and node.image else None}
        for node in material.node_tree.nodes]
    materials.append({'name': material.name, 'nodes': nodes})
images = [{'name': img.name, 'path': img.filepath, 'packed': img.packed_file is not None} for img in bpy.data.images]
report = {'source': str(source), 'objects': objects, 'materials': materials, 'images': images}
source.with_suffix('.inspection.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
print(json.dumps(report, ensure_ascii=False))
