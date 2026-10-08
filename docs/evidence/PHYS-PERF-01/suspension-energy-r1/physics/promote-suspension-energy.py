"""势能与离散能量账作为完整数值块，机械结果仍直接构造原SuspensionStep。"""
from pathlib import Path
root=Path.cwd();folder=root/'logs/physics/PHYS-PERF-01'
p=root/'src/mechanical_kernels.c';s=p.read_text(encoding='utf-8')
marker='/* 原九/十一维共同求根；分区暖状态按每次试探更新，30轮及原精度保持。 */'
s=s.replace(marker,(folder/'suspension-energy-body.c').read_text(encoding='utf-8')+'\n'+marker)
s=s.replace('static PyMethodDef methods[] = {',
    'static PyMethodDef methods[] = {\n    {"suspension_elastic_terms", (PyCFunction)suspension_elastic_terms, METH_VARARGS, "原悬架势能及硬件梯度"},\n    {"suspension_energy_account", (PyCFunction)suspension_energy_account, METH_VARARGS, "原悬架离散能量账"},')
p.write_text(s,encoding='utf-8',newline='\n')
p=root/'src/suspension.py';s=p.read_text(encoding='utf-8')
s=s.replace('from mechanical_kernels import dot, solve_lu, suspension_contact_state',
'''from mechanical_kernels import (
    dot,
    solve_lu,
    suspension_contact_state,
    suspension_elastic_terms,
    suspension_energy_account,
)''')
first=s.index('def elastic_terms(');end=s.index('\n\n\n@dataclass(frozen=True)',first)
s=s[:first]+'elastic_terms = suspension_elastic_terms\n'+s[end:]
first=s.index('    delta = tuple(end[i] - compression[i] for i in range(4))')
s=s[:first]+'''    rate, spring, bar, stop, damping_loss, elastic_loss, body_loss, offset_work, residual, body_work = (
        suspension_energy_account(compression, extension_speed, mobility, dt, geometry, end, forces,
                                  rates, bars, stops, travel, damping))
    return SuspensionStep(end, rate, forces, raw, spring, bar, stop,
                          damping_loss, elastic_loss, body_loss, offset_work, residual, body_work)
'''
p.write_text(s,encoding='utf-8',newline='\n')
