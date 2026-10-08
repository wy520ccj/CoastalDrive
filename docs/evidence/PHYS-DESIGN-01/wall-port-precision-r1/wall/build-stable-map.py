"""只在独立数值模块试验端口重建；生产源码不变。"""
import json
import subprocess
import sys
from pathlib import Path
root=Path.cwd();folder=root/'logs/physics/PHYS-DESIGN-01-wall/stable-map'
folder.mkdir(exist_ok=False)
s=(root/'src/mechanical_kernels.c').read_text(encoding='utf-8')
old='''        for (int a=0; a<9; ++a) end[a]=projected[a]-data->dt*(port_values[0]*branch->mc[a]
                                                +port_values[2]*branch->ml[a]+port_values[1]*branch->mg[a]);'''
assert old in s
replacement='''        for (int a=0; a<9; ++a) {
            double updates[4]={projected[a],-data->dt*port_values[0]*branch->mc[a],
                -data->dt*port_values[2]*branch->ml[a],-data->dt*port_values[1]*branch->mg[a]};
            end[a]=compensated(updates,4);
        }'''
s=s.replace(old,replacement)
s=s.replace('"mechanical_kernels"','"_stable_map"').replace('PyInit_mechanical_kernels','PyInit__stable_map')
(folder/'stable.c').write_text(s,encoding='utf-8')
(folder/'setup.py').write_text('from setuptools import Extension,setup\nsetup(name="stable-map-probe",ext_modules=[Extension("_stable_map",["stable.c"],extra_compile_args=["/fp:strict","/utf-8"])])\n',encoding='utf-8')
with (folder/'build.log').open('w',encoding='utf-8') as log:
    result=subprocess.run([sys.executable,'setup.py','build_ext','--build-lib','b','--build-temp','t'],cwd=folder,stdout=log,stderr=subprocess.STDOUT)
print(json.dumps({'build_returncode':result.returncode}))
raise SystemExit(result.returncode)
