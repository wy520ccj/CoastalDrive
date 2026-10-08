"""数值精度修复后重审旧节点，仅复用不依赖机械内核的旧模块与当前T1。"""
import hashlib
import json
import subprocess
import sys
from pathlib import Path
root=Path.cwd();folder=root/'logs/validation'
source=(folder/'PHYS-INTEGRATE-03-reuse-audit.py').read_text(encoding='utf-8')
prefix=source[:source.index('prior=json.loads(')]
prefix=prefix.replace("if name in ('tire_drivetrain','src.tire_drivetrain'):return True",
    "if name in ('mechanical_kernels','src.mechanical_kernels','tire_drivetrain','src.tire_drivetrain'):return True")
scope={};exec(compile(prefix,'AST conservative audit','exec'),scope)
affected=scope['affected']
prior=json.loads((folder/'PHYS-INTEGRATE-03-reuse-audit.json').read_text(encoding='utf-8'))
remaining=sorted(prior['remaining_node_ids'],key=lambda node:node!='tests/test_h3_review.py::test_highway_traffic_stays_grounded_and_retires_beyond_finish')
assert remaining[267]=='tests/test_h1_vehicle.py::test_collision_wall_stops_car_without_tunneling'
pool=list(dict.fromkeys(prior['reused_node_ids']+remaining[:267]))
safe=[];invalid=[]
for node in pool:
    module=node.split('::')[0].removesuffix('.py').replace('/','.')
    (invalid if affected(module) else safe).append(node)
current=json.loads((folder/'PHYS-INTEGRATE-04-wall-T1/summary.json').read_text(encoding='utf-8'))
assert current['passed']
def collect(tests):
    result=subprocess.run([sys.executable,'-m','pytest','--collect-only','-q',*tests],capture_output=True,text=True,encoding='utf-8',check=True)
    return [line for line in result.stdout.splitlines() if line.startswith('tests/') and '::' in line]
all_nodes=collect(['tests']);fresh=collect(current['tests'])
reused=list(dict.fromkeys(safe+fresh));assert set(reused)<=set(all_nodes)
selected=[node for node in all_nodes if node not in set(reused)]
report={'method':'conservative whole-module transitive AST imports; mechanical_kernels and tire_drivetrain affected; dynamic calls affected',
    'prior_pool':len(pool),'old_unaffected_node_ids':safe,'old_invalidated_node_ids':invalid,
    'current_T1_node_ids':fresh,'reused_node_ids':reused,'remaining_node_ids':selected,
    'total':len(all_nodes),'reuse_count':len(reused),'remaining_count':len(selected),
    'current_T1_summary_sha256':hashlib.sha256((folder/'PHYS-INTEGRATE-04-wall-T1/summary.json').read_bytes()).hexdigest()}
(folder/'PHYS-INTEGRATE-04-reuse-audit.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
(folder/'PHYS-INTEGRATE-04-reused-nodes.json').write_text(json.dumps(reused),encoding='utf-8')
print(json.dumps({k:report[k] for k in ('total','reuse_count','remaining_count','prior_pool')}))
