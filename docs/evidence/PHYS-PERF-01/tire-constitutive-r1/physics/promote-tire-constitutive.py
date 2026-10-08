"""将原轮胎本构数值块移入已有内核；变形传递和能量账保留原入口。"""
from pathlib import Path
root=Path.cwd();folder=root/'logs/physics/PHYS-PERF-01'
path=root/'src/mechanical_kernels.c';source=path.read_text(encoding='utf-8')
index=source.index('static PyMethodDef methods[]')
source=source[:index]+(folder/'tire-constitutive-body.c').read_text(encoding='utf-8')+'\n'+source[index:]
source=source.replace('static PyMethodDef methods[] = {','''static PyMethodDef methods[] = {
    {"tire_combined_force", (PyCFunction)tire_combined_force, METH_VARARGS, "原联合滑移轮胎力"},
    {"tire_contact_force", (PyCFunction)tire_contact_force, METH_VARARGS, "原柔性胎体及接触分区"},
    {"tire_contact_jacobian", (PyCFunction)tire_contact_jacobian, METH_VARARGS, "原柔性接触解析导数"},''',1)
path.write_text(source,encoding='utf-8')
path=root/'src/tire_forces.py';source=path.read_text(encoding='utf-8')
source=source.replace('import math','import math\n\nfrom mechanical_kernels import tire_combined_force',1)
begin=source.index('    if grip == 0:',source.index('def combined_force('))
source=source[:begin]+'''    return tire_combined_force(kappa, alpha, grip, cx, cy, shape, curvature, math.hypot)
'''
path.write_text(source,encoding='utf-8')
path=root/'src/tire_compliance.py';source=path.read_text(encoding='utf-8')
source=source.replace('from tire_forces import combined_force','from mechanical_kernels import tire_contact_force, tire_contact_jacobian',1)
begin=source.index('    deformation, rate = deformation_state(',source.index('def contact_force('))
end=source.index('\n\ndef energy_terms(',begin)
source=source[:begin]+'''    return tire_contact_force(force, previous, slip, denominator, rolling, grip, cx, cy,
                              dt, stiffness, damping, shape, curvature, math.hypot)
'''+source[end:]
begin=source.index('    if grip == 0:',source.index('def contact_jacobian('))
source=source[:begin]+'''    return tire_contact_jacobian(force, previous, slip, slip_jacobian, denominator, denominator_gradient,
                                 rolling, grip, cx, cy, dt, stiffness, damping, shape, curvature, math.hypot)
'''
path.write_text(source,encoding='utf-8')
