import json,math,random,subprocess,sys
from pathlib import Path
import numpy as np
root=Path.cwd();sys.path.insert(0,str(root/'src'))
from triangle_support import clipped_triangle
from wheel_envelope import subtract
source=subprocess.run(['git','show','7055a13:src/triangle_support.py'],capture_output=True,text=True,encoding='utf-8',check=True).stdout
space={'math':math};exec(source[source.index('def clipped_triangle('):source.index('def triangle_entry(')],space);old=space['clipped_triangle'];rng=random.Random(17);count=0
for scale in (1e-6,1.,1e6,1e9):
 for _ in range(256):
  triangle=tuple(tuple(scale*rng.uniform(-2,2) for a in range(3)) for i in range(3))
  start=tuple(scale*rng.uniform(-1,1) for a in range(3));end=tuple(scale*rng.uniform(-1,1) for a in range(3));padding=(scale*.338,scale*.15,scale*.338)
  expected=old(triangle,start,end,padding);actual=clipped_triangle(triangle,start,end,padding)
  assert expected==actual
  assert [[v.hex() for v in p] for p in expected]==[[v.hex() for v in p] for p in actual]
  for p,q in zip(expected,actual):
   if any(p is vertex for vertex in triangle):assert q is p
  count+=1
subcounts=0
for n in (0,1,2,3,4,6,9,11):
 for m in (0,2,3,9):
  for method in (tuple,list,lambda xs:iter(xs),lambda xs:np.array(xs,dtype=np.float64)):
   a=method([rng.uniform(-100,100) for _ in range(n)]);b=method([rng.uniform(-100,100) for _ in range(m)])
   # 迭代器使用相同值的独立副本。
   av,bv=tuple(a),tuple(b);left1,right1=iter(av),iter(bv);left2,right2=iter(av),iter(bv)
   expected=tuple(x-y for x,y in zip(left1,right1));actual=subtract(left2,right2)
   assert expected==actual
   assert [type(x) for x in expected]==[type(x) for x in actual]
   assert tuple(left1)==tuple(left2) and tuple(right1)==tuple(right2)
   subcounts+=1
report={'passed':True,'clip_cases':count,'clip_values_hex_order_and_original_vertex_identity_equal':True,'subtract_cases':subcounts,'subtract_values_types_and_remaining_iterators_equal':True,'reference':'7055a13 Python clip + original Python zip subtraction'}
(root/'logs/physics/PHYS-PERF-01/clipped-geometry-probe.json').write_text(json.dumps(report,indent=2),encoding='utf-8');print(json.dumps(report))
