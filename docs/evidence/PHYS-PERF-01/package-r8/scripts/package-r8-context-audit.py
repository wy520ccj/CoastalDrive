"""核对构建副本与实际包所用原生模块，保留首次读器入口失败。"""
import hashlib
import json
from pathlib import Path
root=Path.cwd();folder=root/'logs/physics/PHYS-PERF-01/package-headless-r8'
context=root/'builds/physics-native-candidate-r8-source'
package=root/'builds/physics-native-candidate-r8/win_amd64'
initial=json.loads((root/'logs/validation/PHYS-INTEGRATE-04-package-r8/summary.json').read_text(encoding='utf-8'))
rows={}
for name,sha in initial['copied_sha256'].items():
    current=hashlib.sha256((context/name).read_bytes()).hexdigest()
    assert current==sha,(name,sha,current)
    rows[name]=current
native={}
for module in ('mechanical_kernels','wheel_contact_kernels'):
    paths=[root/f'src/{module}.cp314-win_amd64.pyd',context/f'src/{module}.cp314-win_amd64.pyd',package/f'{module}.pyd']
    hashes=[hashlib.sha256(p.read_bytes()).hexdigest() for p in paths]
    assert len(set(hashes))==1,(module,hashes)
    native[module]={'paths':list(map(str,paths)),'sha256':hashes[0]}
report={'copied_context_unchanged':True,'copied_sha256':rows,'native_byte_equal':True,'native':native}
(folder/'context-audit.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
(folder/'reader-entry-failure.json').write_text(json.dumps({'status':'failed','returncode':1,
    'script':'docs/evidence/PHYS-PERF-01/integration-r3/package-scripts/native-package-check-r7-r2.py',
    'reason':'archived script parents[3] points to docs/evidence, output mkdir failed with FileNotFoundError',
    'phase':'reader output directory before any package execution','package_checks_run':0,
    'corrected_entry':'logs/physics/PHYS-PERF-01/native-package-check-r8.py'},indent=2),encoding='utf-8')
print(json.dumps({'copied_files':len(rows),'native_byte_equal':True}))
