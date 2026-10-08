import hashlib
import json
import re
from pathlib import Path

root = Path(__file__).resolve().parents[4]
folder = Path(__file__).resolve().parent
audit = json.loads((folder / 'audit.json').read_text(encoding='utf-8'))
capture = folder / 'group3-source'
capture.mkdir(exist_ok=True)
for name, digest in audit['source_sha_end'].items():
    data = (root / name).read_bytes()
    assert hashlib.sha256(data).hexdigest() == digest
    (capture / Path(name).name).write_bytes(data)
(folder / 'audit-group3.json').write_bytes((folder / 'audit.json').read_bytes())
(folder / 'audit-group3.log').write_bytes((folder / 'audit.log').read_bytes())
body = (folder / 'hypot-probe/hypot-body.c').read_text(encoding='utf-8')
start = body.index('static DoubleLength\ndl_sum(')
end = body.index('static DoubleLength\ndl_mul(', start)
body = body[:start] + body[end:]
body = re.sub(r'/\*.*?\*/', '', body, flags=re.S)
body = re.sub(r'//[^\n]*', '', body)
body = body.replace('DoubleLength', 'HypotPair').replace('dl_fast_sum', 'hypot_fast_sum')
body = body.replace('dl_mul', 'hypot_product').replace('vector_norm', 'hypot_vector_norm').replace('norm_two', 'hypot_two')
header = ('/* CPython 3.14.2 vector_norm两维原算法；缩放/补偿平方/微分校正均保持。\n'
          ' * 来源Modules/mathmodule.c，许可见licenses/CPython-LICENSE.txt。 */\n')
path = root / 'src/mechanical_kernels.c'
source = path.read_text(encoding='utf-8').replace('#include <string.h>', '#include <string.h>\n#include <float.h>')
source = source.replace('/* 保留CPython hypot的原舍入；其余本构算式沿原次序直接计算。 */', header + body +
                        '\n/* None显式选择同版本原生算法；旧入口仍调用实际传入的函数。 */')
source = source.replace('''static int tire_norm(PyObject *hypot_function,double x,double y,double *value) {
    PyObject *result''', '''static int tire_norm(PyObject *hypot_function,double x,double y,double *value) {
    if (hypot_function==Py_None) { *value=hypot_two(x,y); return 1; }
    PyObject *result''')
path.write_text(source, encoding='utf-8')
path = root / 'src/tire_drivetrain.py'
source = path.read_text(encoding='utf-8')
source = source.replace('contact_parameters[index], tire_hardware[index], dt, rolling[index], math.hypot)',
                        'contact_parameters[index], tire_hardware[index], dt, rolling[index], None if shaft else math.hypot)')
source = source.replace('suspension is not None and sweep == 0 and rolling[i] and wheel_loads[i] > 0, math.hypot)',
                        'suspension is not None and sweep == 0 and rolling[i] and wheel_loads[i] > 0, None)')
source = source.replace('tire_compliance, math.hypot)', 'tire_compliance, None)')
path.write_text(source, encoding='utf-8')
