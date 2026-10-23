import hashlib,json,sys
from pathlib import Path
import gltf
from panda3d.core import Filename,GeomVertexReader,MaterialAttrib,NodePath,TextureAttrib
root=Path.cwd();out=root/'logs/validation/GARAGE-DESIGN-02-paint-normals'
def read(path):
 model=NodePath(gltf.load_model(Filename.fromOsSpecific(str(path))))
 result={}
 for part in model.findAllMatches('**/+GeomNode'):
  transform=part.getMat(model)
  for index,geom in enumerate(part.node().getGeoms()):
   state=part.node().getGeomState(index);mat=state.getAttrib(MaterialAttrib).getMaterial();name=mat.getName()
   vertex=GeomVertexReader(geom.getVertexData(),'vertex');uv=GeomVertexReader(geom.getVertexData(),'texcoord')
   has_uv=geom.getVertexData().getFormat().hasColumn('texcoord')
   rows=[];normal_rows=[];normal_reader=GeomVertexReader(geom.getVertexData(),'normal')
   while not vertex.isAtEnd():
    p=transform.xformPoint(vertex.getData3f());t=tuple(uv.getData2f()) if has_uv else ();rows.append(tuple(round(float(v),7) for v in (*p,*t)))
    normal_rows.append((*rows[-1],*(round(float(v),6) for v in normal_reader.getData3f())))
   faces=[];normal_faces=[]
   for primitive in geom.getPrimitives():
    triangle=primitive.decompose();indices=triangle.getVertexList()
    for offset in range(0,len(indices),3):
     points=tuple(rows[i] for i in indices[offset:offset+3]);faces.append(min(points,points[1:]+points[:1],points[2:]+points[:2]))
     points=tuple(normal_rows[i] for i in indices[offset:offset+3]);normal_faces.append(min(points,points[1:]+points[:1],points[2:]+points[:2]))
   textures=[];attrib=state.getAttrib(TextureAttrib)
   if attrib is not None:
    for stage in attrib.getOnStages():
     texture=attrib.getOnTexture(stage);textures.append((stage.getName(),texture.getXSize(),texture.getYSize(),hashlib.sha256(bytes(texture.getRamImage())).hexdigest()))
   entry=result.setdefault(name,dict(faces=[],normal_faces=[],textures=[],material=[tuple(mat.getBaseColor()),float(mat.getMetallic()),float(mat.getRoughness())]))
   entry['faces'].extend(faces);entry['normal_faces'].extend(normal_faces);entry['textures'].extend(textures)
 for name,entry in result.items():
  faces=entry.pop('faces');entry['triangles']=len(faces);entry['geometry_uv_sha256']=hashlib.sha256(repr(sorted(faces)).encode()).hexdigest();entry['textures']=sorted(set(entry['textures']))
  entry['normal_sha256']=hashlib.sha256(repr(sorted(entry.pop('normal_faces'))).encode()).hexdigest()
 return result
old=read(out/'baseline/subaru_brz.glb');new=read(root/'art/vehicles/subaru_brz.glb')
old_normals={k:v.pop('normal_sha256') for k,v in old.items()};new_normals={k:v.pop('normal_sha256') for k,v in new.items()}
normal_changes={k:old_normals[k]!=new_normals[k] for k in old_normals}
report={'passed':old==new,'baseline':old,'final':new,'normal_changes_6_decimals':normal_changes,'scope':'per material triangle position/winding/UV rounded 7 decimals; decoded texture pixels and material values exact; normals measured separately at 6 decimals'}
(out/'geometry-comparison.json').write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps({'passed':report['passed'],'triangles':sum(p['triangles'] for p in new.values()),'materials':list(new)}))
assert report['passed']
print(normal_changes)
