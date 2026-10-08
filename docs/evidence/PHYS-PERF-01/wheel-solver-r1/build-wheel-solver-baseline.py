import subprocess
import sys
from pathlib import Path
root=Path(__file__).resolve().parents[3]
folder=root/'logs/physics/PHYS-PERF-01/wheel-solver-baseline';folder.mkdir(parents=True,exist_ok=True)
source=(folder.parent/'wheel-solver-original.c').read_text(encoding='utf-8')
source=source.replace('"mechanical_kernels"','"_wheel_solver_old"').replace('PyInit_mechanical_kernels','PyInit__wheel_solver_old')
(folder/'baseline.c').write_text(source,encoding='utf-8')
(folder/'setup.py').write_text('from setuptools import Extension, setup\nsetup(name="wheel-solver-baseline",ext_modules=[Extension("_wheel_solver_old",["baseline.c"],extra_compile_args=["/fp:strict","/utf-8"])])\n',encoding='utf-8')
with (folder/'build.log').open('w',encoding='utf-8') as output:
    result=subprocess.run([sys.executable,'setup.py','build_ext','--inplace'],cwd=folder,stdout=output,stderr=subprocess.STDOUT)
raise SystemExit(result.returncode)
