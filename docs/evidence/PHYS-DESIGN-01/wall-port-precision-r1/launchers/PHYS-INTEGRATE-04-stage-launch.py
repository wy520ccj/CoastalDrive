"""冻结精度修复版，补齐剩余阶段节点；旧机械长轨迹不跨修复复用。"""
import hashlib
import json
import sys
from pathlib import Path
root=Path.cwd();sys.path.insert(0,str(root/'tools'))
from validate import Check,execute_plan,git_value,make_plan
folder=root/'logs/validation';audit_path=folder/'PHYS-INTEGRATE-04-reuse-audit.json'
audit=json.loads(audit_path.read_text(encoding='utf-8'))
output=folder/'PHYS-INTEGRATE-04-stage-T2'
checks=make_plan('T2',[],[],output)
checks[1]=Check('pytest-remaining',[str(folder/'PHYS-INTEGRATE-01-remaining-pytest.py'),str(folder/'PHYS-INTEGRATE-04-reused-nodes.json')])
t1=json.loads((folder/'PHYS-INTEGRATE-04-wall-T1/summary.json').read_text(encoding='utf-8'));assert t1['passed']
reused_checks=[c for c in t1['checks'] if c['name'].startswith('headless-')]
checks=[c for c in checks if not c.name.startswith('headless-')]
files=sorted(p for area in ('src','tests','tools') for p in (root/area).rglob('*') if p.suffix in ('.py','.c','.pyd','.json','.gz'))
files.append(root/'setup.py')
metadata={'git_head':git_value('rev-parse','HEAD'),'git_status':git_value('status','--short'),
    'sha256':{p.relative_to(root).as_posix():hashlib.sha256(p.read_bytes()).hexdigest() for p in files},
    'collection_count':audit['total'],'remaining_node_count':audit['remaining_count'],
    'reused_passed_node_ids':audit['reused_node_ids'],'reuse_audit_sha256':hashlib.sha256(audit_path.read_bytes()).hexdigest(),
    'reused_follow_up_checks':reused_checks,
    'scope':'Only reviewed unaffected old modules and exact-current T1 reused. Prior mechanical trajectories invalidated across accurate port reconstruction. Same-current 3 startup seeds reused; stage/render/human gates remain separate.'}
raise SystemExit(execute_plan(checks,output,'T2-continuation',14400,metadata))
