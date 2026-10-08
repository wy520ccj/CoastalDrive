"""复用750已通过节点和本轮完整56节点，仅补首次未运行的三种子。"""
import hashlib
import json
import subprocess
import sys
from pathlib import Path
root=Path.cwd();folder=root/'logs/validation';sys.path.insert(0,str(root/'tools'))
from validate import execute_plan,git_value,make_plan
old=json.loads((folder/'PHYS-PERF-01-tire-constitutive-T1/summary.json').read_text(encoding='utf-8'))
fresh=json.loads((folder/'PHYS-PERF-01-tire-phase-T0/summary.json').read_text(encoding='utf-8'))
assert not old['passed'] and fresh['passed']
def collect(tests):
    result=subprocess.run([sys.executable,'-m','pytest','--collect-only','-q',*tests],capture_output=True,text=True,encoding='utf-8',check=True)
    return [line for line in result.stdout.splitlines() if line.startswith('tests/') and '::' in line]
old_nodes=collect(old['tests']);fresh_nodes=collect(fresh['tests'])
failed={f'tests/test_tire_compliance_probe.py::test_real_short_trial_energy_and_control_account[{case}]' for case in ('acceleration','constant-turn')}
assert len(old_nodes)==752 and len(fresh_nodes)==56
passed=[node for node in old_nodes if node not in failed]
assert len(passed)==750
reused=list(dict.fromkeys(passed+fresh_nodes))
output=folder/'PHYS-PERF-01-tire-constitutive-T1-completion'
checks=[check for check in make_plan('T1',[],fresh['tests'],output) if check.name.startswith('headless-')]
files=sorted(p for area in ('src','tests','tools') for p in (root/area).rglob('*') if p.suffix in ('.py','.c','.pyd','.json'))
metadata={'git_head':git_value('rev-parse','HEAD'),'git_status':git_value('status','--short'),
          'source_sha256':{str(p.relative_to(root)):hashlib.sha256(p.read_bytes()).hexdigest() for p in files},
          'reused_passed_node_ids':reused,'distinct_passed_node_count':len(reused),
          'failed_old_nodes':sorted(failed),'old_T1_summary_sha256':hashlib.sha256((folder/'PHYS-PERF-01-tire-constitutive-T1/summary.json').read_bytes()).hexdigest(),
          'fresh_T0_summary_sha256':hashlib.sha256((folder/'PHYS-PERF-01-tire-phase-T0/summary.json').read_bytes()).hexdigest(),
          'scope':'composite T1:750 actual prior passes +56 actual full phase/probe passes; no duplicate pytest. Physicalsource unchanged since first T1; only two timestamp assertions and two protocol descriptions corrected. Original Python baseline reproduced same two failures; zero tolerances changed. Three previously not_run seeds execute now.'}
raise SystemExit(execute_plan(checks,output,'T1-composite',900,metadata))
