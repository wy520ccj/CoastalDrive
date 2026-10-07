"""归档事件原生事实、夹具修正及续跑清单。"""
import ast
import hashlib
import json
import shutil
import subprocess
import sys
from pathlib import Path
root = Path.cwd()
logs = root/'logs/validation'
archive = root/'docs/evidence/PHYS-DESIGN-01/impact-manifold-r1'
archive.mkdir(parents=True, exist_ok=False)
t0 = json.loads((logs/'PHYS-INTEGRATE-02-impact-scrape-T0/summary.json').read_text(encoding='utf-8'))
assert t0['passed']
prior = json.loads((logs/'PHYS-INTEGRATE-02-impact-reuse-audit.json').read_text(encoding='utf-8'))
stage = json.loads((logs/'PHYS-INTEGRATE-02-stage-T2-r3/summary.json').read_text(encoding='utf-8'))
assert all(hashlib.sha256((root/name).read_bytes()).hexdigest() == value for name, value in stage['sha256'].items() if name.startswith('src\\'))
def functions(source):
    return {n.name: ast.dump(n, include_attributes=False) for n in ast.parse(source).body if isinstance(n, ast.FunctionDef)}
old = functions(subprocess.check_output(['git','show','5196529:tests/test_impact_events.py'], text=True, encoding='utf-8'))
new = functions((root/'tests/test_impact_events.py').read_text(encoding='utf-8'))
changed = [name for name in old if old[name] != new[name]]
assert changed == ['test_bullet_post_solve_rail_manifold_is_one_real_event', 'test_five_second_rail_scrape_stays_contact_without_repeated_impacts']
collected = subprocess.run([sys.executable,'-m','pytest','--collect-only','-q','tests'],capture_output=True,text=True,encoding='utf-8',check=True)
nodes = [line for line in collected.stdout.splitlines() if line.startswith('tests/') and '::' in line]
assert len(nodes) == 2130
module = [node for node in nodes if node.startswith('tests/test_impact_events.py::')]
assert len(module) == 13
reused = list(dict.fromkeys(prior['reused_node_ids'] + module))
assert set(reused) <= set(nodes)
remaining = [node for node in nodes if node not in set(reused)]
audit = {'total':len(nodes),'reuse_count':len(reused),'remaining_count':len(remaining),
         'reused_node_ids':reused,'remaining_node_ids':remaining,
         'production_source_unchanged':True,'changed_test_functions':changed,
         'previous_stage_sha256':hashlib.sha256((logs/'PHYS-INTEGRATE-02-stage-T2-r3/summary.json').read_bytes()).hexdigest(),
         'complete_module_passed_nodes':module}
(logs/'PHYS-INTEGRATE-02-manifold-reuse-audit.json').write_text(json.dumps(audit,indent=2),encoding='utf-8')
(logs/'PHYS-INTEGRATE-02-manifold-reused-nodes.json').write_text(json.dumps(reused,indent=2),encoding='utf-8')
seeds = json.loads((logs/'PHYS-INTEGRATE-02-T1/summary.json').read_text(encoding='utf-8'))
t1 = {'tier':'T1','passed':True,'status':'passed','scope':'complete module/Ruff actually passed; identical-production three seed evidence reused',
      'module_and_Ruff':t0,'headless_checks':[c for c in seeds['checks'] if c['name'].startswith('headless-')],
      'stage_gate':'not_assessed','human_gate':'pending'}
(logs/'PHYS-INTEGRATE-02-impact-scrape-T1-receipt.json').write_text(json.dumps(t1,indent=2),encoding='utf-8')
files = [root/'tests/test_impact_events.py', logs/'PHYS-INTEGRATE-02-manifold-close.py',
         logs/'PHYS-INTEGRATE-02-manifold-reuse-audit.json',logs/'PHYS-INTEGRATE-02-impact-scrape-T1-receipt.json']
for folder in ('PHYS-INTEGRATE-02-stage-T2-r3','PHYS-INTEGRATE-02-impact-timestamp-T0',
               'PHYS-INTEGRATE-02-impact-manifold-T0','PHYS-INTEGRATE-02-impact-manifold-T1',
               'PHYS-INTEGRATE-02-impact-scrape-T0'):
    files.extend(p for p in (logs/folder).rglob('*') if p.is_file())
files.extend(p for p in logs.glob('PHYS-INTEGRATE-02-scrape-*') if p.is_file())
manifest=[]
for path in files:
    dest = archive / path.relative_to(root)
    if dest.suffix == '.log': dest=dest.with_suffix('.log.txt')
    dest.parent.mkdir(parents=True,exist_ok=True)
    shutil.copyfile(path,dest)
    digest=hashlib.sha256(path.read_bytes()).hexdigest()
    assert hashlib.sha256(dest.read_bytes()).hexdigest()==digest
    manifest.append({'source':str(path.relative_to(root)),'archive':str(dest.relative_to(archive)),'sha256':digest})
(archive/'manifest.json').write_text(json.dumps(manifest,indent=2),encoding='utf-8')
receipt={'baseline':'5196529','production_unchanged':True,'T0_module_nodes':13,'T1':t1,
         'old_T2':'0 passed / 1 stale manifold timestamp assertion failed; followups not run',
         'old_module_T1':'12 passed / legacy continuous scrape only227 ticks failed',
         'two_degree_world_heading_probe':'legacy243 / finite1419; retained failure',
         'five_degree_world_heading_probe':'both1420 continuous contact ticks; exactly one impact at tick3',
         'scope':'first event measured against real native solver; clear2cm approach and real input steering hold; original600 contact/one impact and speed/zone/event identity constraints retained',
         'reuse_count':len(reused),'remaining_count':len(remaining),'followups_pending':11,
         'stage_gate':'pending','human_gate':'pending'}
(archive/'receipt.json').write_text(json.dumps(receipt,indent=2),encoding='utf-8')
print(json.dumps({'archive':str(archive),'files':len(manifest),'reuse':len(reused),'remaining':len(remaining)}))
