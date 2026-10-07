"""离线制作GR86外观近似模型与运行网格。"""
import json
import math
from pathlib import Path

import bpy
from mathutils import Vector
from mathutils.geometry import tessellate_polygon

ART_OUT=Path.cwd()/'art/vehicles'
GAME_OUT=Path.cwd()/'assets/game/vehicles'
PREVIEW_OUT=Path.cwd()/'logs/physics/PHYS-REAL-01-appearance'
for output_dir in (ART_OUT,GAME_OUT,PREVIEW_OUT):
    output_dir.mkdir(parents=True,exist_ok=True)
bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.context.scene.unit_settings.system='METRIC'

def material(name,color,roughness,metallic=0):
    mat=bpy.data.materials.new(name);mat.use_nodes=True
    node=mat.node_tree.nodes['Principled BSDF']
    node.inputs['Base Color'].default_value=(*color,1)
    node.inputs['Roughness'].default_value=roughness
    node.inputs['Metallic'].default_value=metallic
    return mat
PAINT=material('Body Paint',(.65,.69,.73),.28,.38)
GLASS=material('Blue Grey Glass',(.008,.015,.022),.16,.18)
BLACK=material('Satin Black Plastic',(.013,.016,.02),.65)
RUBBER=material('Tire Rubber',(.009,.01,.012),.9)
METAL=material('Graphite Wheel Metal',(.08,.09,.11),.23,.8)
LAMP=material('Head Light',(.75,.86,.93),.14,.18)
RED=material('Tail Light',(.5,.007,.012),.22,.2)
LENS=material('Smoked Lamp Housing',(.025,.04,.055),.19,.25)
STEEL=material('Exhaust Steel',(.36,.39,.42),.22,.85)
RED.node_tree.nodes['Principled BSDF'].inputs['Emission Color'].default_value=(.3,.002,.003,1)
RED.node_tree.nodes['Principled BSDF'].inputs['Emission Strength'].default_value=.3

def empty(name,parent=None):
    obj=bpy.data.objects.new(name,None);bpy.context.collection.objects.link(obj);obj.parent=parent
    return obj
root=empty('gr86-2022-premium-draft');paint=empty('paint',root)

def mesh(name,vertices,faces,mat,parent=root):
    data=bpy.data.meshes.new(name);data.from_pydata(vertices,[],faces);data.update()
    obj=bpy.data.objects.new(name,data);bpy.context.collection.objects.link(obj);obj.parent=parent
    obj.data.materials.append(mat)
    bpy.context.view_layer.objects.active=obj;obj.select_set(True)
    bpy.ops.object.mode_set(mode='EDIT');bpy.ops.mesh.select_all(action='SELECT');bpy.ops.mesh.normals_make_consistent(inside=False);bpy.ops.object.mode_set(mode='OBJECT');obj.select_set(False)
    return obj

def box(name,center,size,mat,parent=root,bevel=0):
    bpy.ops.mesh.primitive_cube_add(size=1,location=center);obj=bpy.context.object;obj.name=name;obj.parent=parent
    obj.dimensions=size;bpy.ops.object.transform_apply(location=False,rotation=False,scale=True)
    obj.data.materials.append(mat)
    if bevel:
        mod=obj.modifiers.new('Panel radii','BEVEL');mod.width=bevel;mod.segments=2
        bpy.ops.object.modifier_apply(modifier=mod.name)
    obj.select_set(False)
    return obj

def cylinder(name,center,radius,depth,mat,parent=root,axis='X',segments=32):
    rotation=(0,math.pi/2,0) if axis=='X' else (math.pi/2,0,0)
    bpy.ops.mesh.primitive_cylinder_add(vertices=segments,radius=radius,depth=depth,location=center,rotation=rotation)
    obj=bpy.context.object;obj.name=name;obj.parent=parent;obj.data.materials.append(mat);obj.select_set(False)
    return obj

# 车身横截面；尺寸取原厂资料，曲面造型为自制近似。
sections=[(-2.1325,.78,.64),(-1.92,.86,.77),(-1.45,.8875,.85),(-.95,.87,.84),(-.45,.845,.80),
          (.15,.85,.79),(.75,.86,.80),(1.2875,.8875,.79),(1.7,.865,.72),(2.02,.82,.65),(2.1325,.77,.61)]
vertices=[]
for y,w,h in sections:
    vertices += [(x,y,z) for x,z in [(-w*.90,.13),(-w,.29),(-w,.55),(-w*.96,h),(-w*.72,h+.015),
                                  (0,h+.025),(w*.72,h+.015),(w*.96,h),(w,.55),(w,.29),(w*.90,.13)]]
n=11;faces=[tuple(range(n-1,-1,-1)),tuple(range((len(sections)-1)*n,len(sections)*n))]
faces += [(r*n+i,r*n+(i+1)%n,(r+1)*n+(i+1)%n,(r+1)*n+i) for r in range(len(sections)-1) for i in range(n)]
body=mesh('Body with wheel arches',vertices,faces,PAINT,paint)
for y in (-1.2875,1.2875):
    cutter=cylinder('Arch cutter',(0,y,.3146),.351,2.4,BLACK)
    bpy.context.view_layer.objects.active=body
    mod=body.modifiers.new('Wheel arch','BOOLEAN');mod.operation='DIFFERENCE';mod.object=cutter
    bpy.ops.object.modifier_apply(modifier=mod.name);bpy.data.objects.remove(cutter,do_unlink=True)
# 肩线和保险杠保留原横截面，圆角只削去内侧锐边。
bpy.context.view_layer.objects.active=body
mod=body.modifiers.new('Body edge radii','BEVEL');mod.width=.026;mod.segments=3
bpy.ops.object.modifier_apply(modifier=mod.name)
for polygon in body.data.polygons:polygon.use_smooth=True
mod=body.modifiers.new('Body panel normals','WEIGHTED_NORMAL');mod.keep_sharp=True
bpy.ops.object.modifier_apply(modifier=mod.name)
# 圆角会削去孤立的最宽肩线，车身网格恢复名义不含镜车宽，轮根不参与缩放。
width=max(v.co.x for v in body.data.vertices)-min(v.co.x for v in body.data.vertices)
for vertex in body.data.vertices:vertex.co.x*=1.775/width
body.data.update()

# 灯片沿已有车身横截面外侧布置，避免藏在实心车身内。
def hood_height(x,y):
    found,point,_normal,_index=body.ray_cast(Vector((x,y,2.)),Vector((0.,0.,-1.)))
    if not found:raise ValueError('灯片位置超出实际车身网格')
    return point.z

def hood_panel(name,outline,mat,lift):
    vertices,faces=[],[]
    polygon=[Vector((x,y,0.)) for x,y in outline]
    for triangle in tessellate_polygon([polygon]):
        tri=tuple(polygon[index] for index in triangle)
        indices={}
        for i in range(5):
            for j in range(5-i):
                point=tri[0]*(1-(i+j)/4)+tri[1]*(i/4)+tri[2]*(j/4)
                indices[i,j]=len(vertices);vertices.append((point.x,point.y,hood_height(point.x,point.y)+lift))
        for i in range(4):
            for j in range(4-i):
                faces.append((indices[i,j],indices[i+1,j],indices[i,j+1]))
                if i+j<3:faces.append((indices[i+1,j],indices[i+1,j+1],indices[i,j+1]))
    return mesh(name,vertices,faces,mat)

# 低矮双门车顶与独立玻璃。
mesh('Roof and pillars',[(-.74,-1.25,.83),(.74,-1.25,.83),(-.62,-.65,1.19),(.62,-.65,1.19),
                        (-.59,-.28,1.31),(.59,-.28,1.31),(-.60,.23,1.30),(.60,.23,1.30),
                        (-.72,.9,.81),(.72,.9,.81)],
     [(0,1,3,2),(2,3,5,4),(4,5,7,6),(6,7,9,8),(0,2,4,6,8),(1,9,7,5,3),(0,8,9,1)],PAINT,paint)
mesh('Windshield',[(-.665,.86,.858),(.665,.86,.858),(.555,.275,1.287),(-.555,.275,1.287)],[(0,1,2,3)],GLASS)
mesh('Rear glass',[(-.65,-1.19,.88),(.65,-1.19,.88),(.56,-.685,1.18),(-.56,-.685,1.18)],[(0,1,2,3)],GLASS)
for side in (-1,1):
    mesh('Side glass',[(side*.744,-1.04,.88),(side*.650,-.58,1.19),(side*.622,-.24,1.27),(side*.628,.19,1.257),(side*.741,.70,.87)],[(0,1,2,3,4)],GLASS)
    box('Door handle',(side*.858,-.38,.70),(.022,.16,.026),METAL,bevel=.008)
    box('Side mirror',(side*.94,.54,.86),(.15,.23,.095),BLACK,bevel=.03)
    mesh('Fender vent',[(side*.876,.91,.60),(side*.876,.79,.62),(side*.876,.91,.28)],[(0,1,2)],BLACK)
    box('Side skirt',(side*.855,0,.17),(.055,1.7,.08),PAINT,paint,bevel=.012)
    x=side
    lamp_xy=((x*.43,2.115),(x*.735,2.10),(x*.82,1.86),(x*.63,1.84))
    hood_panel('Headlamp housing',lamp_xy,LENS,.003)
    drl_xy=((x*.46,2.09),(x*.72,2.072),(x*.786,1.885),(x*.764,1.884),(x*.695,2.043),(x*.462,2.064))
    hood_panel('Headlamp running light',drl_xy,LAMP,.008)
    mesh('Projector lens',[(x*.66,1.94,hood_height(x*.66,1.94)+.009),
                           (x*.724,1.94,hood_height(x*.724,1.94)+.009),
                           (x*.724,2.005,hood_height(x*.724,2.005)+.009),
                           (x*.66,2.005,hood_height(x*.66,2.005)+.009)],[(0,1,2,3)],LAMP)
    mesh('Corner intake',[(x*.625,2.13252,.50),(x*.735,2.13252,.52),(x*.735,2.13252,.30),(x*.64,2.13252,.28)],[(0,1,2,3)],BLACK)
    mesh('Tail lamp housing',[(x*.42,-2.13252,.68),(x*.78,-2.13252,.72),(x*.80,-2.06,.78),(x*.49,-2.13252,.77)],[(0,1,2,3)],LENS)
    mesh('Tail running light',[(x*.45,-2.13254,.745),(x*.765,-2.13254,.742),(x*.765,-2.13254,.708),
                              (x*.72,-2.13254,.693),(x*.74,-2.13254,.727),(x*.46,-2.13254,.730)],[(0,1,2,3,4,5)],RED)
    cylinder('Exhaust outlet',(side*.63,-2.08755,.23),.055,.09,STEEL,axis='Y')
    cylinder('Exhaust dark center',(side*.63,-2.1306,.23),.043,.004,BLACK,axis='Y')
mesh('Front grille',[(-.60,2.13251,.56),(.60,2.13251,.56),(.49,2.13251,.25),(-.49,2.13251,.25)],[(0,1,2,3)],BLACK)
box('Rear diffuser',(0,-2.12001,.26),(1.50,.025,.18),BLACK,bevel=.012)
box('Rear plate',(0,-2.12501,.53),(.40,.015,.14),LAMP,bevel=.007)
box('Premium ducktail',(0,-2.01,.835),(1.65,.19,.065),PAINT,paint,bevel=.024)

# 四个轮根符合现有显示接口，轮轴沿X；18英寸轮圈及215/40R18名义尺寸。
names=('wheel-front-left','wheel-front-right','wheel-back-left','wheel-back-right')
for name,y,side,track in zip(names,(1.2875,1.2875,-1.2875,-1.2875),(-1,1,-1,1),(1.52,1.52,1.55,1.55)):
    wheel=empty(name,root);wheel.location=(side*track/2,y,.3146)
    verts=[];profile=[(-.1075,.235),(-.106,.284),(-.09,.308),(-.07,.3146),(.07,.3146),(.09,.308),(.106,.284),(.1075,.235)]
    for x,r in profile:
        verts.extend((x,r*math.cos(i*math.tau/48),r*math.sin(i*math.tau/48)) for i in range(48))
    faces=[(r*48+i,r*48+(i+1)%48,(r+1)*48+(i+1)%48,(r+1)*48+i) for r in range(len(profile)-1) for i in range(48)]
    mesh('Tire shell',verts,faces,RUBBER,wheel)
    cylinder('18 inch rim',(side*.086,0,0),.2286,.02,METAL,wheel)
    cylinder('Dark rim recess',(side*.098,0,0),.211,.004,BLACK,wheel)
    cylinder('Wheel hub',(side*.095,0,0),.061,.016,METAL,wheel,segments=20)
    for i in range(10):
        angle=i*math.tau/10
        obj=box('Wheel spoke',(side*.094,.126*math.cos(angle),.126*math.sin(angle)),(.016,.174,.019),METAL,wheel,bevel=.003)
        obj.rotation_euler.x=angle
# 草稿输出与两张离线预览。
bpy.ops.wm.save_as_mainfile(filepath=str(ART_OUT/'gr86_2022_premium.blend'))

scene=bpy.context.scene;scene.render.engine='CYCLES';scene.cycles.samples=16
scene.render.resolution_x=1100;scene.render.resolution_y=750;scene.render.resolution_percentage=100
scene.world=bpy.data.worlds.new('Neutral studio world')
scene.world.color=(.18,.18,.18)
bpy.ops.object.light_add(type='AREA',location=(2,3,5));light=bpy.context.object;light.data.energy=1100;light.data.shape='DISK';light.data.size=5
bpy.ops.object.camera_add();scene.camera=bpy.context.object;scene.camera.data.lens=52
for name,pos in [('front',(4.4,6.1,2.8)),('rear',(-4.4,-6.1,2.5))]:
    scene.camera.location=pos;scene.camera.rotation_euler=(Vector((0,0,.62))-scene.camera.location).to_track_quat('-Z','Y').to_euler()
    scene.render.filepath=str(PREVIEW_OUT/f'{name}.png');bpy.ops.render.render(write_still=True)
manifest={'status':'Appearance draft only, not game-integrated or accepted','source':'Original procedural mesh; OEM brochure p2/p4/p13/p14 used for proportion/trim references',
          'source_url':'https://www.toyota.com/content/dam/toyota/brochures/pdf/2022/gr86_ebrochure.pdf',
          'units':'metres; Z up, +Y forward','wheelbase_m':2.575,'front_track_m':1.52,'rear_track_m':1.55,
          'nominal_tire_radius_m':.3146,'nominal_tire_width_m':.215,'editable_source':'gr86_2022_premium.blend',
          'geometry_kind':'Approximate low-poly representation, not manufacturer CAD','blender_version':bpy.app.version_string}
bpy.ops.wm.save_as_mainfile(filepath=str(ART_OUT/'gr86_2022_premium.blend'))
(PREVIEW_OUT/'manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')

# 运行导出按轮根/材质合并；可编辑源文件仍保留部件。
groups={}
for obj in list(bpy.data.objects):
    if obj.type=='MESH': groups.setdefault((obj.parent,obj.data.materials[0]),[]).append(obj)
for (parent,mat),objects in groups.items():
    bpy.ops.object.select_all(action='DESELECT')
    for obj in objects: obj.select_set(True)
    bpy.context.view_layer.objects.active=objects[0];bpy.ops.object.join()
    obj=bpy.context.object;transform=obj.matrix_world.copy();obj.parent=parent;obj.matrix_world=transform
    obj.name=mat.name+' surfaces'
bpy.ops.export_scene.gltf(filepath=str(GAME_OUT/'gr86_2022_premium.glb'),export_format='GLB',export_yup=True,export_apply=True)
