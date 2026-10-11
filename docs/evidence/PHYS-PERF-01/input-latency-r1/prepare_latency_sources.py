from pathlib import Path
import shutil
import subprocess

root = Path.cwd()
out = root/'logs/performance/input-latency-r1/baseline/src'
shutil.copytree(root/'src',out,ignore=shutil.ignore_patterns('__pycache__'))
for name in ('controls.py','driver_assist.py','driving_modes.py','session_process.py'):
    (out/name).write_bytes(subprocess.check_output(['git','show',f'HEAD:src/{name}']))
p = out/'paths.py'
p.write_text(p.read_text(encoding='utf-8').replace('Path(__file__).resolve().parent.parent','Path.cwd()'),encoding='utf-8')
