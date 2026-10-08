"""将完整步的数值构造收口到同一原生块，保持Python结果与公开势能入口。"""
from pathlib import Path
root=Path.cwd();folder=root/'logs/physics/PHYS-PERF-01'
p=root/'src/mechanical_kernels.c';s=p.read_text(encoding='utf-8')
s=s.replace('static PyMethodDef methods[] = {',
    (folder/'suspension-step-body.c').read_text(encoding='utf-8')+'\nstatic PyMethodDef methods[] = {\n    {"suspension_step", (PyCFunction)suspension_step, METH_VARARGS, "原完整悬架步与能量账"},')
p.write_text(s,encoding='utf-8',newline='\n')
p=root/'src/suspension.py';s=p.read_text(encoding='utf-8')
s=s.replace('    suspension_contact_state,\n','').replace('    suspension_energy_account,\n','    suspension_step,\n')
first=s.index('    stiffness = stiffness_matrix(rates, bars)',s.index('def advance_suspension('))
s=s[:first]+'''    geometry = compression if geometry is None else geometry
    return SuspensionStep(*suspension_step(compression, extension_speed, mobility, touching,
        rates, compression_damping, extension_damping, bars, stops, travel, dt, geometry))
'''
p.write_text(s,encoding='utf-8',newline='\n')
