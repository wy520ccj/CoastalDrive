import subprocess
import sys
from pathlib import Path
root = Path(__file__).resolve().parents[3]
folder = root / 'logs/physics/PHYS-PERF-01/triangle-packet-baseline'
folder.mkdir(parents=True, exist_ok=True)
source = (folder.parent / 'triangle-packet-original.c').read_text(encoding='utf-8')
source = source.replace('"wheel_contact_kernels"', '"_triangle_packet_old"').replace('PyInit_wheel_contact_kernels', 'PyInit__triangle_packet_old')
(folder / 'baseline.c').write_text(source, encoding='utf-8')
(folder / 'setup.py').write_text('from setuptools import Extension, setup\nsetup(name="triangle-packet-baseline",ext_modules=[Extension("_triangle_packet_old",["baseline.c"],extra_compile_args=["/fp:strict","/utf-8"])])\n',encoding='utf-8')
with (folder / 'build.log').open('w',encoding='utf-8') as log:
    result = subprocess.run([sys.executable,'setup.py','build_ext','--inplace'],cwd=folder,stdout=log,stderr=subprocess.STDOUT)
raise SystemExit(result.returncode)
