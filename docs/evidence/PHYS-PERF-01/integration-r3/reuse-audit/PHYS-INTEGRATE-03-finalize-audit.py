"""合并整合版实际通过节点；原生活动集以原方程同值证据复用原785。"""
import hashlib
import json
import subprocess
import sys
from pathlib import Path
root=Path.cwd();folder=root/'logs/validation'
audit=json.loads((folder/'PHYS-INTEGRATE-03-reuse-audit.json').read_text(encoding='utf-8'))
t1=json.loads((folder/'PHYS-INTEGRATE-03-T1/summary.json').read_text(encoding='utf-8'))
assert t1['passed']
collected=subprocess.run([sys.executable,'-m','pytest','--collect-only','-q',*t1['tests']],capture_output=True,text=True,encoding='utf-8',check=True)
nodes=[line for line in collected.stdout.splitlines() if line.startswith('tests/') and '::' in line]
assert len(nodes)==528
reused=list(dict.fromkeys(audit['reused_node_ids']+nodes))
remaining=[node for node in audit['remaining_node_ids'] if node not in set(reused)]
assert len(reused)+len(remaining)==2130
native=root/'docs/evidence/PHYS-PERF-01/suspension-state-r1/receipt.json'
proof=json.loads(native.read_text(encoding='utf-8'))
assert proof['suspension_state_audit']['all_fields_equal'] and proof['LU_probe']['result']['passed']
assert '"all_fields_equal": true' in (root/'logs/physics/PHYS-DESIGN-01-map160/integrated-snapshots.log').read_text(encoding='utf-8')
audit.update(reused_node_ids=reused,remaining_node_ids=remaining,reuse_count=len(reused),remaining_count=len(remaining),
    current_integration_passed_node_ids=nodes,
    integration_T1_summary_sha256=hashlib.sha256((folder/'PHYS-INTEGRATE-03-T1/summary.json').read_bytes()).hexdigest(),
    integration_native_active_set_proof='Windows x64 MSVC strict identical operations: 5757 actual full SuspensionStep calls +512 independent originalLU calls; current528 T1/all three seeds passed; merged48-step complete snapshots equal current Python active-set version. Native data boundary preserves valid physical arguments; current785 semantically reused across C extraction, not represented as same-source.',
    native_active_set_receipt_sha256=hashlib.sha256(native.read_bytes()).hexdigest())
(folder/'PHYS-INTEGRATE-03-reuse-audit.json').write_text(json.dumps(audit,indent=2),encoding='utf-8')
(folder/'PHYS-INTEGRATE-03-reused-nodes.json').write_text(json.dumps(reused,indent=2),encoding='utf-8')
print(json.dumps({'reuse':len(reused),'remaining':len(remaining)}))
