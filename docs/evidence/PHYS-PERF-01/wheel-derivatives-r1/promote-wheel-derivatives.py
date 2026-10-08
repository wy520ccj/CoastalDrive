"""按轮端职责保存原固定响应，并迁移同一活动分区解析导数。"""
from pathlib import Path
root=Path.cwd()
p=root/'src/mechanical_kernels.c'
s=p.read_text(encoding='utf-8')
marker='/* 局部轮力与端口分区共用原共同映射判据，暖模式按每次尝试直接更新。 */'
s=s.replace(marker, marker+'''\ntypedef struct {
    SharedBranch ports;
    double force_responses[2][9];
} WheelBranch;''')
s=s.replace('    SharedBranch local[];','    WheelBranch local[];')
s=s.replace('sizeof(WheelMap)+4*shared->branch_count*sizeof(SharedBranch)',
            'sizeof(WheelMap)+4*shared->branch_count*sizeof(WheelBranch)')
s=s.replace('SharedBranch *local=&data->local[4*b+w];','''WheelBranch *wheel_branch=&data->local[4*b+w];
            SharedBranch *local=&wheel_branch->ports;
            PyObject *wheel=PyTuple_GET_ITEM(PyTuple_GET_ITEM(input,4),w);
            for (int j=0; j<2; ++j)
                if (!vector(PyTuple_GET_ITEM(wheel,j),wheel_branch->force_responses[j],9)) goto failed;''')
s=s.replace('            PyObject *wheel=PyTuple_GET_ITEM(PyTuple_GET_ITEM(input,4),w);\n            if (!vector(PyTuple_GET_ITEM(wheel,2)',
            '            if (!vector(PyTuple_GET_ITEM(wheel,2)')
s=s.replace('*local=&packet->local[4*index+wheel];','*local=&packet->local[4*index+wheel].ports;')
new=(root/'logs/physics/PHYS-PERF-01/wheel-derivatives-body.c').read_text(encoding='utf-8')
marker='/* 原四轮接触/阻尼/止挡活动集；分区次序、64轮与精度保持。 */'
s=s.replace(marker,new+'\n'+marker)
s=s.replace('static PyMethodDef methods[] = {',
    'static PyMethodDef methods[] = {\n    {"wheel_map_derivatives", (PyCFunction)wheel_map_derivatives, METH_VARARGS, "原轮端机械活动分区完整解析导数"},')
p.write_text(s,encoding='utf-8',newline='\n')
p=root/'src/tire_drivetrain.py'
s=p.read_text(encoding='utf-8').replace('    wheel_map_coefficients,','    wheel_map_coefficients,\n    wheel_map_derivatives,')
first=s.index('        def derivatives(fx, fy):')
last=s.index('\n        def jacobian(fx, fy):',first)
body=s[first:last]
body=body.replace('            _branch, mc, ml, _response, wheel_responses, local_response, plans, shaft_data = branches[branch_index]',
'''            if shaft:
                return wheel_map_derivatives(wheel_map, i, branch_index, index, end, velocity_end,
                                             moments_x[i], moments_y[i], radii[i], frame.tangent, frame.axle)
            _branch, mc, ml, _response, wheel_responses, local_response, plans, _shaft_data = branches[branch_index]''')
old_start=body.index('                if shaft:')
old_end=body.index('                elif ratio:',old_start)
body=body[:old_start]+body[old_end:].replace('                elif ratio:','                if ratio:',1)
body=body.replace('                dg = 0.\n','')
body=body.replace(' - (dg * mg[a] if shaft else 0.)','')
s=s[:first]+body+s[last:]
s=s.replace('    shaft_brake_response,\n','').replace('    synchronizer_brake_response,\n','')
p.write_text(s,encoding='utf-8',newline='\n')
