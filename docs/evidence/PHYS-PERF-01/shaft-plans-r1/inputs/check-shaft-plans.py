import itertools,json,random,subprocess,sys,time
from pathlib import Path
root=Path.cwd();sys.path.insert(0,str(root/'src'))
from transmission_ports import _inverse_three
import mechanical_kernels
source=subprocess.run(['git','show','16a7c4a:src/shaft_transmission.py'],capture_output=True,text=True,encoding='utf-8',check=True).stdout
space={'product':itertools.product,'_inverse_three':_inverse_three}
exec(source[source.index('def shaft_brake_plans('):source.index('def shaft_brake_response(')],space)
old=space['shaft_brake_plans'];new=mechanical_kernels.shaft_brake_plans
rng=random.Random(17); inputs=[]
for scale in (1e-6,1.,1e6):
 for capacity,brake,efficiency in itertools.product((0.,37.),(0.,91.),(.85,.98,1.)):
  for _ in range(32):
   a=[[rng.uniform(-1,1) for j in range(4)] for i in range(4)]
   response=tuple(tuple(scale*(sum(a[k][i]*a[k][j] for k in range(4))+(1. if i==j else 0.)) for j in range(4)) for i in range(4))
   args=(response,capacity,brake,efficiency)
   before,after=old(*args),new(*args)
   assert before==after,(args,before,after)
   assert len(before)==len(after)
   # 同约束逆矩阵的对象复用也与原分区表一致。
   for i in range(len(before)):
    for j in range(i):
     assert (before[i][3] is before[j][3])==(after[i][3] is after[j][3])
   inputs.append(args)
times=[]
for implementation in (old,new,old,new):
 start=time.perf_counter()
 for args in inputs: implementation(*args)
 times.append(time.perf_counter()-start)
report={'status':'passed','matrices':len(inputs),'all_values_and_cache_identity_equal':True,'order':'Python C Python C','micro_wall_seconds':times,'source_head':'16a7c4a + native shaft plans','not_fps':True}
(root/'logs/physics/PHYS-PERF-01/shaft-plans-probe.json').write_text(json.dumps(report,indent=2),encoding='utf-8'); print(json.dumps(report))
