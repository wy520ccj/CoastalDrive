import hashlib,json,random,subprocess,sys,time
from pathlib import Path
root=Path.cwd();sys.path.insert(0,str(root/'src'))
import suspension_contacts
from wheel_contact_kernels import support_candidates
source=subprocess.run(['git','show','4635006:src/suspension_contacts.py'],capture_output=True,text=True,encoding='utf-8',check=True).stdout
space=dict(suspension_contacts.__dict__)
exec(source[source.index('def cylinder_candidates('):source.index('def collision_shape_bounds(')],space)
old=space['cylinder_candidates'];new=suspension_contacts.cylinder_candidates
rng=random.Random(17);groups=[]
identity=((1.,0.,0.),(0.,1.,0.),(0.,0.,1.))
frames=[identity]+[tuple(tuple(rng.uniform(-1,1) for _ in range(3)) for i in range(3)) for _ in range(7)]
for i in range(96):
 parts=[]
 for j in range(1+i%4):
  origin=tuple(rng.uniform(-100,100) for _ in range(3));half=tuple(rng.uniform(.01,8) for _ in range(3))
  bounds=(tuple(-v for v in half),half) if i%17 else None
  parts.append((object(),frames[(i+j)%8],origin,half,.01,None,None,bounds))
 groups.append((object(),bool(i%3),tuple(parts)))
groups=tuple(groups);queries=[]
for _ in range(512):
 low=tuple(rng.uniform(-120,80) for _ in range(3));high=tuple(v+rng.uniform(0,40) for v in low)
 expected=old(None,None,None,low,high,static_shapes=groups)
 actual=new(None,None,None,low,high,static_shapes=groups)
 assert expected==actual
 # 检查边界投影数值及原part对象、分组顺序，而不仅是最终集合。
 center=tuple((a+b)/2 for a,b in zip(low,high));half=tuple((b-a)/2 for a,b in zip(low,high))
 records=[]
 for body,supported,parts in groups:
  selected=[]
  for part in parts:
   _,frame,translation,_,_,_,_,bounds=part
   local_center=tuple(translation[a]+sum(frame[a][b]*center[b] for b in range(3)) for a in range(3))
   local_half=tuple(sum(abs(frame[a][b])*half[b] for b in range(3)) for a in range(3))
   if bounds is not None and any(local_center[a]+local_half[a]<bounds[0][a] or local_center[a]-local_half[a]>bounds[1][a] for a in range(3)): continue
   selected.append((part,local_center,local_half))
  if selected:records.append((body,supported,selected))
 assert records==support_candidates(groups,low,high)
 queries.append((low,high))
times=[]
for method in (old,new,old,new):
 start=time.perf_counter()
 for low,high in queries:method(None,None,None,low,high,static_shapes=groups)
 times.append(time.perf_counter()-start)
report={'passed':True,'queries':len(queries),'parts_per_query':sum(len(g[2]) for g in groups),'all_projections_part_identity_order_and_final_candidates_equal':True,'micro_wall_seconds_python_c_python_c':times,'not_fps':True}
(root/'logs/physics/PHYS-PERF-01/support-candidates-probe.json').write_text(json.dumps(report,indent=2),encoding='utf-8');print(json.dumps(report))
