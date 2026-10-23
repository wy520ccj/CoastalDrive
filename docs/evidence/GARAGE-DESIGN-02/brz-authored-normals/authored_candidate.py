import bpy,json,math
import numpy as np
from pathlib import Path
from mathutils import Matrix,Vector
root=Path.cwd();out=root/'logs/validation/GARAGE-DESIGN-02-paint-normals'
fit=json.loads((root/'art/vehicles/brz-fit.json').read_text())
bpy.ops.wm.open_mainfile(filepath=str(root/'art/vehicles/sources/subaru-brz/sx.blend'),load_ui=False,use_scripts=False)
mesh=bpy.data.objects['SX_body'].data
rotation=Matrix.Rotation(-math.pi/2,4,'Z')@Matrix.Rotation(math.pi,4,'X')
positions=[];normals=[]
for loop,normal in zip(mesh.loops,mesh.corner_normals):
 x,y,z=rotation@mesh.vertices[loop.vertex_index].co
 sx=fit['collision_half_width']/.978189647;sz=2*fit['collision_half_height']/1.312586397
 sy=fit['wheelbase']/2/1.275 if abs(y)<=1.275 else (fit['collision_half_length']-fit['wheelbase']/2)/((2.291652679 if y>0 else 2.177099943)-1.275)
 yy=y*sy if abs(y)<=1.275 else math.copysign(fit['wheelbase']/2+(abs(y)-1.275)*sy,y)
 positions.append((x*sx,yy,fit['body_center_height']-fit['collision_half_height']+(z+.481446356)*sz))
 n=rotation.to_3x3()@normal.vector
 normals.append(tuple(Vector((n.x/sx,n.y/sy,n.z/sz)).normalized()))
bpy.ops.wm.open_mainfile(filepath=str(root/'art/vehicles/subaru_brz.blend'),load_ui=False,use_scripts=False)
obj=next(o for o in bpy.data.objects if o.type=='MESH' and o.name.split('.')[0]=='SX_body');mesh=obj.data
current=np.asarray([tuple(mesh.vertices[loop.vertex_index].co) for loop in mesh.loops])
errors=np.linalg.norm(current-np.asarray(positions),axis=1)
report={'loops':len(normals),'max_position_error':float(errors.max()),'mismatches_above_2um':int((errors>2e-6).sum()),'blender':bpy.app.version_string}
print(report)
assert report['mismatches_above_2um']==0
old=np.asarray([tuple(n.vector) for n in mesh.corner_normals]);new=np.asarray(normals)
angles=np.degrees(np.arccos(np.clip(np.sum(old*new,axis=1),-1,1)))
report['angle_degrees']={str(p):float(np.percentile(angles,p)) for p in (50,90,95,99,100)}
mesh.normals_split_custom_set(normals);mesh.update()
bpy.ops.export_scene.gltf(filepath=str(out/'candidate-authored.glb'),export_format='GLB',export_yup=True,export_apply=True,export_extras=True,export_cameras=False,export_lights=False,use_active_scene=True)
bpy.ops.wm.save_as_mainfile(filepath=str(out/'candidate-authored.blend'))
(out/'authored-report.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
print(report)
