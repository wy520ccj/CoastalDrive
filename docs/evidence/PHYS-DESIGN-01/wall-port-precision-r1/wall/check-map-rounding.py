"""独立100位算术核对保存输入的端口重建相消，不修改生产模块。"""
import json
import subprocess
import sys
from decimal import Decimal,localcontext
from pathlib import Path

root=Path.cwd();folder=root/'logs/physics/PHYS-DESIGN-01-wall'
sys.path.insert(0,str(root/'src'))
import mechanical_kernels

build=folder/'map-terms';build.mkdir(exist_ok=False)
s=(root/'src/mechanical_kernels.c').read_text(encoding='utf-8')
marker='static PyObject *shared_map_state(PyObject *self,PyObject *args,PyObject *kwargs) {'
s=s.replace(marker,'static double map_terms[9][8];\n'+marker)
old='''        for (int a=0; a<9; ++a) end[a]=projected[a]-data->dt*(port_values[0]*branch->mc[a]
                                                +port_values[2]*branch->ml[a]+port_values[1]*branch->mg[a]);'''
assert old in s
s=s.replace(old,'''        for (int a=0; a<9; ++a) {
            double values[8]={projected[a],data->dt,port_values[0],branch->mc[a],port_values[2],branch->ml[a],port_values[1],branch->mg[a]};
            for (int j=0; j<8; ++j) map_terms[a][j]=values[j];
            end[a]=projected[a]-data->dt*(port_values[0]*branch->mc[a]+port_values[2]*branch->ml[a]+port_values[1]*branch->mg[a]);
        }''')
getter='''static PyObject *read_map_terms(PyObject *self,PyObject *args) {
    PyObject *rows=PyTuple_New(9);
    if (!rows) return NULL;
    for (int i=0; i<9; ++i) {
        PyObject *row=Py_BuildValue("(dddddddd)",map_terms[i][0],map_terms[i][1],map_terms[i][2],map_terms[i][3],map_terms[i][4],map_terms[i][5],map_terms[i][6],map_terms[i][7]);
        if (!row) { Py_DECREF(rows); return NULL; }
        PyTuple_SET_ITEM(rows,i,row);
    }
    return rows;
}
'''
s=s.replace('static PyMethodDef methods[] = {',getter+'\nstatic PyMethodDef methods[] = {\n    {"read_map_terms", (PyCFunction)read_map_terms,METH_VARARGS,"独立舍入观测"},')
s=s.replace('"mechanical_kernels"','"_map_terms"').replace('PyInit_mechanical_kernels','PyInit__map_terms')
(build/'terms.c').write_text(s,encoding='utf-8')
(build/'setup.py').write_text('from setuptools import Extension,setup\nsetup(name="map-terms",ext_modules=[Extension("_map_terms",["terms.c"],extra_compile_args=["/fp:strict","/utf-8"])])\n',encoding='utf-8')
with (build/'build.log').open('w',encoding='utf-8') as log:
    subprocess.run([sys.executable,'setup.py','build_ext','--build-lib','b','--build-temp','t'],cwd=build,stdout=log,stderr=subprocess.STDOUT,check=True)
sys.path[:0]=[str(build/'b'),str(folder/'stable-map/b')]
import _map_terms
import _stable_map

def unpack(value):
    if isinstance(value,dict):
        if 'capsule' in value:return getattr(mechanical_kernels,value['capsule'])(*unpack(value['args']),**unpack(value['kwargs']))
        if 'tuple' in value:return tuple(unpack(x) for x in value['tuple'])
        return {k:unpack(v) for k,v in value.items()}
    if isinstance(value,list):return [unpack(x) for x in value]
    return value
packet=unpack(json.loads((folder/'shared-input.json').read_text(encoding='utf-8')))
args=(packet['shared_map'],packet['state'],packet['loads'],packet['wheel_loads'],packet['supported'],packet['shared_branch'])
old=_map_terms.shared_map_state(*args)
new=_stable_map.shared_map_state(*args)
terms=_map_terms.read_map_terms()
rows=[]
with localcontext() as context:
    context.prec=100
    for i,row in enumerate(terms):
        p,dt,c,mc,l,ml,g,mg=map(Decimal.from_float,row)
        exact=p-dt*(c*mc+l*ml+g*mg)
        rows.append({'coordinate':i,'components':row,'exact':str(exact),
                     'old':old[0][i],'compensated':new[0][i],
                     'old_error':str(Decimal.from_float(old[0][i])-exact),
                     'compensated_error':str(Decimal.from_float(new[0][i])-exact)})
report={'decimal_precision':100,'rows':rows}
(folder/'map-rounding.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
print(json.dumps(rows[4]))
