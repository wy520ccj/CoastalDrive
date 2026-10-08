"""复制冻结源码构建候选包，记录主线与独立构建上下文的完整指纹。"""
import hashlib
import json
import shutil
import subprocess
import sys
import time
from pathlib import Path
root=Path.cwd();context=root/'builds/physics-native-candidate-r8-source'
package=root/'builds/physics-native-candidate-r8'
out=root/'logs/validation/PHYS-INTEGRATE-04-package-r8';out.mkdir(exist_ok=False)
assert not context.exists() and not package.exists()

def hashes(base):
    files=[p for area in ('src','tests','tools') for p in (base/area).rglob('*')
           if p.suffix in ('.py','.c','.pyd','.json','.gz')]
    files.append(base/'setup.py')
    return {p.relative_to(base).as_posix():hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(files)}

before=hashes(root)
stage=json.loads((root/'logs/validation/PHYS-INTEGRATE-04-stage-T2/summary.json').read_text(encoding='utf-8'))
assert stage['sha256']==before
context.mkdir()
shutil.copytree(root/'src',context/'src',ignore=shutil.ignore_patterns('__pycache__','*.pyc'))
shutil.copytree(root/'licenses',context/'licenses')
for name in ('setup.py','pyproject.toml'):shutil.copy2(root/name,context/name)
asset_path=str(context/'assets').replace("'","''")
asset_source=str(root/'assets').replace("'","''")
subprocess.run(['powershell','-NoProfile','-Command',
    f"New-Item -ItemType Junction -Path '{asset_path}' -Value '{asset_source}' | Out-Null"],check=True)
copied=hashes(context)
assert all(before[name]==digest for name,digest in copied.items())
record={'main_head':subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip(),
    'physics_stage_start_head':stage['git_head'],'before_sha256':before,'copied_sha256':copied,
    'source_context':str(context),'package':str(package),'status':'running'}
(out/'summary.json').write_text(json.dumps(record,indent=2),encoding='utf-8')
command=[sys.executable,'setup.py','build_apps','--build-base',str(package)]
started=time.perf_counter()
with (out/'build.log').open('wb') as log:
    result=subprocess.run(command,cwd=context,stdout=log,stderr=subprocess.STDOUT,check=False)
after=hashes(root);context_after=hashes(context)
record.update(command=command,returncode=result.returncode,seconds=time.perf_counter()-started,
    after_sha256=after,context_after_sha256=context_after,main_source_frozen=before==after,
    status='passed' if result.returncode==0 and before==after else 'failed')
(out/'summary.json').write_text(json.dumps(record,indent=2),encoding='utf-8')
print(json.dumps({k:record[k] for k in ('status','seconds','main_source_frozen')}))
raise SystemExit(0 if record['status']=='passed' else 1)
