from pathlib import Path
root=Path.cwd();p=root/'src/wheel_contact_kernels.c';s=p.read_text(encoding='utf-8')
s=s.replace('static double sum_three(double values[3]) {','static double sum_values(const double *values,int count) {',1)
begin=s.index('static double sum_values(');end=s.index('static double dot(',begin)
block=s[begin:end].replace('i < 3','i < count');block+='static double sum_three(double values[3]) { return sum_values(values,3); }\n\n'
s=s[:begin]+block+s[end:]
begin=s.index('    double projection=dot(value,axis)',s.index('static PyObject *rotated_path_call('));end=s.index('    return Py_BuildValue',begin)
body=s[begin:end].replace(',end[3],average[3]', '')
helper='static void rotated_path_values(double value[3],double axis[3],double angle,double scale,\n                                double end[3],double average[3]) {\n    if (angle==0.) { for (int a=0; a<3; ++a) { end[a]=value[a]; average[a]=value[a]; } return; }\n'+body+'}\n'
s=s[:begin]+'    double end[3],average[3];\n    rotated_path_values(value,axis,angle,scale,end,average);\n'+s[end:]
s=s.replace('static PyObject *rotated_path_call(',helper+'static PyObject *rotated_path_call(',1)
block=(root/'logs/physics/PHYS-PERF-01/endpoint-body.c').read_text(encoding='utf-8')
s=s.replace('static PyMethodDef methods[] = {',block+'\nstatic PyMethodDef methods[] = {\n    {"crown_extent_secant", (PyCFunction)crown_extent_secant, METH_VARARGS, "原胎冠支持高度割线"},\n    {"cylinder_endpoint", (PyCFunction)cylinder_endpoint, METH_VARARGS, "原有限圆柱接点与功共轭离散梯度"},',1)
p.write_text(s,encoding='utf-8')
p=root/'src/wheel_envelope.py';s=p.read_text(encoding='utf-8');begin=s.index('def crown_extent_secant(');end=s.index('def _segment(',begin);s=s[:begin]+'crown_extent_secant = wheel_contact_kernels.crown_extent_secant\n\n\n'+s[end:];p.write_text(s,encoding='utf-8')
p=root/'src/suspension_kinematics.py';s=p.read_text(encoding='utf-8').replace('from wheel_contact_kernels import rotated_path','from wheel_contact_kernels import cylinder_endpoint as endpoint_kernel\nfrom wheel_contact_kernels import rotated_path',1)
begin=s.index('    surface = contact.surface',s.index('def cylinder_endpoint('));end=s.index('\n\ndef face_extension_difference(',begin)
s=s[:begin]+'''    return endpoint_kernel(contact, hub_end, hub_average, direction_end, direction_average,
                           rotation_axis, angle, scale, velocity, angular, dt, face_extension_difference)
'''+s[end:];p.write_text(s,encoding='utf-8')
