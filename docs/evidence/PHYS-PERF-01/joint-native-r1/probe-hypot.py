import hashlib
import json
import math
import random
import shutil
import struct
import subprocess
import sys
import urllib.request
from pathlib import Path

folder = Path(__file__).resolve().parent / 'hypot-probe'
folder.mkdir(exist_ok=True)
url = 'https://raw.githubusercontent.com/python/cpython/v3.14.2/Modules/mathmodule.c'
original = urllib.request.urlopen(url, timeout=30).read()
(folder / 'mathmodule.c').write_bytes(original)
source = original.decode('utf-8')
start = source.index('static inline double\nvector_norm(')
end = source.index('\n#define NUM_STACK_ELEMS', start)
norm = source[start:end]
helpers = source[source.index('typedef struct{ double hi; double lo; } DoubleLength;'):source.index('\n#else', source.index('#ifndef UNRELIABLE_FMA'))]
helpers = helpers.replace('#ifndef UNRELIABLE_FMA\n', '')
body = helpers + '\n' + norm + r'''
static double norm_two(double x,double y) {
    double vec[2]={fabs(x),fabs(y)},maximum=0.;
    for (int i=0;i<2;++i) if (vec[i]>maximum) maximum=vec[i];
    return vector_norm(2,vec,maximum,isnan(x) || isnan(y));
}
'''
(folder / 'hypot-body.c').write_text(body, encoding='utf-8')
extension = '#include <Python.h>\n#include <math.h>\n#include <float.h>\n' + body + r'''
static PyObject *probe(PyObject *self,PyObject *args) {
    double x,y;
    if (!PyArg_ParseTuple(args,"dd",&x,&y)) return NULL;
    return PyFloat_FromDouble(norm_two(x,y));
}
static PyMethodDef methods[]={{"norm",probe,METH_VARARGS,NULL},{NULL,NULL,0,NULL}};
static struct PyModuleDef module={PyModuleDef_HEAD_INIT,"_hypot_probe",NULL,-1,methods};
PyMODINIT_FUNC PyInit__hypot_probe(void) {return PyModule_Create(&module);}
'''
(folder / 'probe.c').write_text(extension, encoding='utf-8')
(folder / 'setup.py').write_text(
    'from setuptools import Extension,setup\n'
    'setup(name="hypot-probe",ext_modules=[Extension("_hypot_probe",["probe.c"],'
    'extra_compile_args=["/fp:strict","/utf-8"])])\n', encoding='utf-8')
with (folder / 'build.log').open('w', encoding='utf-8') as output:
    subprocess.run([sys.executable, 'setup.py', 'build_ext', '--inplace'], cwd=folder,
                   stdout=output, stderr=subprocess.STDOUT, check=True)
sys.path.insert(0, str(folder))
import _hypot_probe

counts = {'boundary': 0, 'random_bits': 0}
values = (0., -0., math.inf, -math.inf, math.nan, sys.float_info.max, sys.float_info.min,
          math.ulp(0.), math.nextafter(sys.float_info.min, 0.), 1., math.nextafter(1., math.inf),
          1e-200, 1e-4, 1e4)
for x in values:
    for y in values:
        expected, actual = math.hypot(x, y), _hypot_probe.norm(x, y)
        assert actual.hex() == expected.hex(), (x.hex(), y.hex(), actual.hex(), expected.hex())
        counts['boundary'] += 1
rng = random.Random(17)
for _ in range(100000):
    x, y = (struct.unpack('d', struct.pack('Q', rng.getrandbits(64)))[0] for _ in range(2))
    expected, actual = math.hypot(x, y), _hypot_probe.norm(x, y)
    assert actual.hex() == expected.hex(), (x.hex(), y.hex(), actual.hex(), expected.hex())
    counts['random_bits'] += 1
report = {'source_url': url, 'source_sha256': hashlib.sha256(original).hexdigest(),
          'python': sys.version, 'compile': '/fp:strict', 'counts': counts, 'all_hex_equal': True}
(folder / 'receipt.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
print(json.dumps(report))
