"""保守按模块导入依赖重审物理修复后的旧节点；实际物理入口重新验证。"""
import ast
import hashlib
import json
import subprocess
import sys
from pathlib import Path
root=Path.cwd();folder=root/'logs/validation'
module_paths={}
for area in ('src','tools','tests'):
    for path in (root/area).rglob('*.py'):
        parts=list(path.relative_to(root/area).with_suffix('').parts)
        if parts[-1]=='__init__':parts.pop()
        if not parts:continue
        name='.'.join(parts)
        module_paths[name]=path;module_paths[area+'.'+name]=path
dependencies={}
for name,path in module_paths.items():
    tree=ast.parse(path.read_text(encoding='utf-8-sig'));imports=set();dynamic=False
    for node in ast.walk(tree):
        if isinstance(node,ast.Import):imports.update(alias.name for alias in node.names)
        elif isinstance(node,ast.ImportFrom):
            prefix=node.module or ''
            if node.level:
                base=name.split('.')[:-node.level];prefix='.'.join(base+([prefix] if prefix else []))
            imports.add(prefix);imports.update(prefix+'.'+a.name for a in node.names)
        elif isinstance(node,ast.Call):
            called=node.func
            if ((isinstance(called,ast.Name) and called.id in ('__import__','exec','eval'))
                or (isinstance(called,ast.Attribute) and called.attr in ('import_module','run','Popen','check_output','check_call'))):dynamic=True
    dependencies[name]=(imports,dynamic)
def affected(name,seen=None):
    seen=set() if seen is None else seen
    if name in ('tire_drivetrain','src.tire_drivetrain'):return True
    if name in seen:return False
    seen.add(name)
    if name not in dependencies:return False
    imports,dynamic=dependencies[name]
    return dynamic or any(affected(module,seen) for module in imports)
prior=json.loads((folder/'PHYS-INTEGRATE-02-manifold-reuse-audit.json').read_text(encoding='utf-8'))
stage=json.loads((folder/'PHYS-INTEGRATE-02-stage-T2-r4/summary.json').read_text(encoding='utf-8'))
failure='tests/test_phase3_map.py::test_every_sampled_map_point_supports_the_car[160]'
assert prior['remaining_node_ids'].index(failure)==18
pool=list(dict.fromkeys(prior['reused_node_ids']+prior['remaining_node_ids'][:18]))
safe=[];invalid=[]
for node in pool:
    name=node.split('::')[0].removesuffix('.py').replace('/','.')
    (invalid if affected(name) else safe).append(node)
current=json.loads((folder/'PHYS-DESIGN-01-map160-T1/summary.json').read_text(encoding='utf-8'))
assert current['passed']
collection=subprocess.run([sys.executable,'-m','pytest','--collect-only','-q','tests'],capture_output=True,text=True,encoding='utf-8',check=True)
all_nodes=[line for line in collection.stdout.splitlines() if line.startswith('tests/') and '::' in line]
fresh=subprocess.run([sys.executable,'-m','pytest','--collect-only','-q',*current['tests']],capture_output=True,text=True,encoding='utf-8',check=True)
fresh_nodes=[line for line in fresh.stdout.splitlines() if line.startswith('tests/') and '::' in line]
assert len(all_nodes)==2130 and len(fresh_nodes)==785
reused=list(dict.fromkeys(safe+fresh_nodes))
assert set(reused)<=set(all_nodes)
remaining=[node for node in all_nodes if node not in set(reused)]
report={'method':'conservative whole-module transitive AST import audit; dynamic imports/exec/subprocess treated affected; old physical trajectories never automatically reused',
        'old_pool':len(pool),'old_unaffected_node_ids':safe,'old_invalidated_node_ids':invalid,
        'current_785_passed_node_ids':fresh_nodes,'reused_node_ids':reused,'remaining_node_ids':remaining,
        'reuse_count':len(reused),'remaining_count':len(remaining),'total':len(all_nodes),
        'old_stage_summary_sha256':hashlib.sha256((folder/'PHYS-INTEGRATE-02-stage-T2-r4/summary.json').read_bytes()).hexdigest(),
        'current_T1_summary_sha256':hashlib.sha256((folder/'PHYS-DESIGN-01-map160-T1/summary.json').read_bytes()).hexdigest(),
        'integration_native_active_set_proof_required':'current785 measured before e576 C active-set merge; full-field actual-call and selected integration T1 proof required before reuse in merged source'}
(folder/'PHYS-INTEGRATE-03-reuse-audit.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
print(json.dumps({'old_pool':len(pool),'safe_old':len(safe),'invalidated_old':len(invalid),'current':len(fresh_nodes),'reuse':len(reused),'remaining':len(remaining)}))
