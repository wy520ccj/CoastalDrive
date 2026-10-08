"""补齐Panda构建边界所需requirements，保留首次缺失输入失败。"""
import hashlib
import json
import shutil
import subprocess
import sys
import time
from pathlib import Path
root=Path.cwd();context=root/'builds/physics-native-candidate-r8-source';package=root/'builds/physics-native-candidate-r8'
out=root/'logs/validation/PHYS-INTEGRATE-04-package-r8-r2';out.mkdir(exist_ok=False)
previous=json.loads((root/'logs/validation/PHYS-INTEGRATE-04-package-r8/summary.json').read_text(encoding='utf-8'))
files=[root/name for name in previous['before_sha256']]
def hashes():return {p.relative_to(root).as_posix():hashlib.sha256(p.read_bytes()).hexdigest() for p in files}
before=hashes();assert before==previous['before_sha256']
shutil.copy2(root/'requirements.txt',context/'requirements.txt')
requirements_sha=hashlib.sha256((context/'requirements.txt').read_bytes()).hexdigest()
assert requirements_sha==hashlib.sha256((root/'requirements.txt').read_bytes()).hexdigest()
command=[sys.executable,'setup.py','build_apps','--build-base',str(package)]
record={'main_head':subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip(),
    'source_context':str(context),'before_sha256':before,'requirements_sha256':requirements_sha,'status':'running'}
(out/'summary.json').write_text(json.dumps(record,indent=2),encoding='utf-8')
start=time.perf_counter()
with (out/'build.log').open('wb') as log:
    result=subprocess.run(command,cwd=context,stdout=log,stderr=subprocess.STDOUT,check=False)
after=hashes()
record.update(command=command,returncode=result.returncode,seconds=time.perf_counter()-start,
    after_sha256=after,main_source_frozen=before==after,
    status='passed' if result.returncode==0 and before==after else 'failed')
(out/'summary.json').write_text(json.dumps(record,indent=2),encoding='utf-8')
print(json.dumps({k:record[k] for k in ('status','seconds','main_source_frozen')}))
raise SystemExit(0 if record['status']=='passed' else 1)
