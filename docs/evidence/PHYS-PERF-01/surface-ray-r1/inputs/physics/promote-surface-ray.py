from pathlib import Path
root=Path.cwd();p=root/'src/wheel_contact_kernels.c';s=p.read_text(encoding='utf-8')
begin=s.index('    for (int a=0; a<3; ++a) {',s.index('static PyObject *surface_transform('));end=s.index('    return Py_BuildValue',begin)
body=s[begin:end]
helper='static void transform_values(const double value[3],const double axes[3][3],const double offset[3],\n                             int transpose,double result[3]) {\n'+body+'}\n'
s=s.replace(body,'    transform_values(value,axes,offset,transpose,result);\n',1)
s=s.replace('static PyObject *surface_transform(',helper+'static PyObject *surface_transform(',1)
block=(root/'logs/physics/PHYS-PERF-01/surface-ray-body.c').read_text(encoding='utf-8').replace('OOOOOdddddOO p','OOOOOdddddOOp')
s=s.replace('static PyMethodDef methods[] = {',block+'\nstatic PyMethodDef methods[] = {\n    {"surface_ray_hits", (PyCFunction)surface_ray_hits, METH_VARARGS, "原有限支持面射线变换及有序接点装配"},',1)
p.write_text(s,encoding='utf-8')
p=root/'src/suspension_contacts.py';s=p.read_text(encoding='utf-8').replace('from wheel_contact_kernels import support_candidates','from wheel_contact_kernels import support_candidates, surface_ray_hits',1)
begin=s.index('        for body, inverse, frame, half, margin, plane, triangles in surfaces:',s.index('def cylinder_suspension_rays('));end=s.index('        results.append(',begin)
s=s[:begin]+'''        if surfaces:
            reach = math.sqrt(sum((end[a] - start[a])**2 for a in range(3))) - radius
            hits.extend(surface_ray_hits(surfaces, relative_start, relative_end, axis, origin,
                radius, reach, width, shoulder, crown, CylinderSurface, RayContact, ray_origin is not None))
'''+s[end:]
p.write_text(s,encoding='utf-8')
