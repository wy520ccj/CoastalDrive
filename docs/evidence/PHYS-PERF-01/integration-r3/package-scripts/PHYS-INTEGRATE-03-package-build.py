"""构建前后记录冻结源码；不修改默认公开包或试玩入口。"""
import hashlib
import json
import subprocess
import sys
import time
from pathlib import Path
root=Path.cwd();out=root/'logs/validation/PHYS-INTEGRATE-03-package-r7';out.mkdir(exist_ok=False)
def hashes():return {p.relative_to(root).as_posix():hashlib.sha256(p.read_bytes()).hexdigest() for area in ('src','tests','tools') for p in sorted((root/area).rglob('*')) if p.suffix in ('.py','.c','.pyd','.json')}
before=hashes();head=subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip()
record={'head':head,'before_sha256':before,'status':'running','source_frozen':True}
(out/'summary.json').write_text(json.dumps(record,indent=2),encoding='utf-8')
command=[sys.executable,'setup.py','build_apps','--build-base','builds/physics-native-candidate-r7']
start=time.perf_counter()
with (out/'build.log').open('wb') as log:result=subprocess.run(command,stdout=log,stderr=subprocess.STDOUT,check=False)
after=hashes();record.update(command=command,returncode=result.returncode,seconds=time.perf_counter()-start,after_sha256=after,
                           source_frozen=before==after,status='passed' if result.returncode==0 and before==after else 'failed')
(out/'summary.json').write_text(json.dumps(record,indent=2),encoding='utf-8')
print(json.dumps({'status':record['status'],'seconds':record['seconds'],'source_frozen':record['source_frozen']}))
raise SystemExit(0 if record['status']=='passed' else 1)

