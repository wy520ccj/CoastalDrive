import hashlib
import json
import subprocess
import sys
from pathlib import Path

root = Path(__file__).resolve().parents[3]
folder = root / 'logs/physics/PHYS-PERF-01/shared-load-r1'
folder.mkdir(parents=True, exist_ok=True)
hashes = {}
for name in ('mechanical_kernels.c', 'tire_drivetrain.py'):
    data = (root / 'src' / name).read_bytes()
    (folder / ('original-' + name)).write_bytes(data)
    hashes['src/' + name] = hashlib.sha256(data).hexdigest()
(folder / 'baseline-sha.json').write_text(json.dumps(hashes, indent=2), encoding='utf-8')
source = (folder / 'original-mechanical_kernels.c').read_text(encoding='utf-8')
source = source.replace('"mechanical_kernels"', '"_shared_load_old"').replace('PyInit_mechanical_kernels', 'PyInit__shared_load_old')
(folder / 'baseline.c').write_text(source, encoding='utf-8')
(folder / 'setup.py').write_text(
    'from setuptools import Extension, setup\n'
    'setup(name="shared-load-old",ext_modules=[Extension("_shared_load_old",["baseline.c"],'
    'extra_compile_args=["/fp:strict","/utf-8"])])\n', encoding='utf-8')
with (folder / 'baseline-build.log').open('w', encoding='utf-8') as output:
    result = subprocess.run([sys.executable, 'setup.py', 'build_ext', '--inplace'], cwd=folder,
                            stdout=output, stderr=subprocess.STDOUT)
raise SystemExit(result.returncode)
