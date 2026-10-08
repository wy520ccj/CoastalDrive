"""冻结整合版，重审后补齐剩余阶段；旧物理长轨迹不跨修复复用。"""
import hashlib
import json
import sys
from pathlib import Path
root=Path.cwd();sys.path.insert(0,str(root/'tools'))
from validate import Check,execute_plan,git_value,make_plan
folder=root/'logs/validation'
audit_path=folder/'PHYS-INTEGRATE-03-reuse-audit.json'
audit=json.loads(audit_path.read_text(encoding='utf-8'))
assert audit['reuse_count']==957 and audit['remaining_count']==1173
output=folder/'PHYS-INTEGRATE-03-stage-T2-r1'
checks=make_plan('T2',[],[],output)
checks[1]=Check('pytest-remaining',[str(folder/'PHYS-INTEGRATE-01-remaining-pytest.py'),str(folder/'PHYS-INTEGRATE-03-reused-nodes.json')])
t1=json.loads((folder/'PHYS-INTEGRATE-03-T1/summary.json').read_text(encoding='utf-8'))
assert t1['passed']
reused_checks=[c for c in t1['checks'] if c['name'].startswith('headless-')]
checks=[c for c in checks if not c.name.startswith('headless-')]
files=sorted(p for area in ('src','tests','tools') for p in (root/area).rglob('*') if p.suffix in ('.py','.c','.pyd','.json'))
metadata={'git_head':git_value('rev-parse','HEAD'),'git_status':git_value('status','--short'),
          'sha256':{str(p.relative_to(root)):hashlib.sha256(p.read_bytes()).hexdigest() for p in files},
          'collection_count':2130,'remaining_node_count':1173,'reused_passed_node_ids':audit['reused_node_ids'],
          'reuse_audit_sha256':hashlib.sha256(audit_path.read_bytes()).hexdigest(),
          'reused_follow_up_checks':reused_checks,
          'scope':'957 reviewed distinct nodes reused, remaining1173/11 followups. Old physical trajectories invalidated across coupled contact refinement. Current785 proof semantically reused across strict identical-operation C active-set extraction, supplemented current528/full snapshots/independent actual-call+LU audits; no same-source claim for that subset. Three exact-current-source seeds reused.'}
raise SystemExit(execute_plan(checks,output,'T2-continuation',14400,metadata))
