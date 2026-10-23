import bpy,json
from pathlib import Path
root=Path.cwd()
report={}
for tag,path in [('source',root/'art/vehicles/sources/subaru-brz/sx.blend'),('derived',root/'art/vehicles/subaru_brz.blend')]:
 bpy.ops.wm.open_mainfile(filepath=str(path),load_ui=False,use_scripts=False)
 obj=next(o for o in bpy.data.objects if o.type=='MESH' and o.name.split('.')[0]=='SX_body');mesh=obj.data
 report[tag]={'vertices':len(mesh.vertices),'faces':len(mesh.polygons),'loops':len(mesh.loops),'custom_normals':mesh.has_custom_normals,'smooth_faces':sum(p.use_smooth for p in mesh.polygons),'sharp_edges':sum(e.use_edge_sharp for e in mesh.edges),'attributes':[(a.name,a.domain,a.data_type) for a in mesh.attributes]}
 print(tag,report[tag])
(root/'logs/validation/GARAGE-DESIGN-02-paint-normals/inspection.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
