from pathlib import Path

root = Path(__file__).resolve().parents[3]
folder = Path(__file__).resolve().parent
target = root / 'src/wheel_contact_kernels.c'
source = target.read_text(encoding='utf-8')
body = (folder / 'geometry-loop-body.c').read_text(encoding='utf-8')
source = source.replace('static PyMethodDef methods[] = {', body + '\nstatic PyMethodDef methods[] = {\n'
    '    {"box_interval", (PyCFunction)box_interval_call, METH_VARARGS | METH_KEYWORDS, "原三轴线段包围盒区间"},\n'
    '    {"rotated_path", (PyCFunction)rotated_path_call, METH_VARARGS | METH_KEYWORDS, "原有限转动末向量与共轭平均"},')
target.write_text(source, encoding='utf-8')
for filename, function, following in (('suspension_geometry.py', 'box_interval', 'box_entry'),
                                       ('suspension_kinematics.py', 'rotated_path', 'finite_contact_system')):
    target = root / 'src' / filename
    source = target.read_text(encoding='utf-8')
    begin = source.index('\ndef ' + function + '(')
    end = source.index('\ndef ' + following + '(', begin)
    source = source[:begin] + '\n\n' + source[end:]
    if filename == 'suspension_geometry.py':
        source = source.replace('from wheel_contact_kernels import surface_transform',
                                'from wheel_contact_kernels import box_interval, surface_transform')
    else:
        source = source.replace('from dataclasses import dataclass, replace',
                                'from dataclasses import dataclass, replace\n\nfrom wheel_contact_kernels import rotated_path')
    target.write_text(source, encoding='utf-8')
