from pathlib import Path
root=Path.cwd();p=root/'src/wheel_contact_kernels.c';s=p.read_text(encoding='utf-8')
begin=s.index('    for (int i=0; i<3; ++i) {',s.index('static PyObject *triangle_support_entry('));end=s.index('    PyObject *candidates=',begin)
old=s[begin:end]
helper='''static int triangle_support_padding(double axis[3],double radius,double width,double shoulder,
                                    double crown,double margin,double padding[3]) {
'''+old.replace('return NULL;','return 0;')+'''    return 1;
}
'''
s=s.replace(old,'    if (!triangle_support_padding(axis,radius,width,shoulder,crown,margin,padding)) return NULL;\n',1)
s=s.replace('static PyObject *triangle_support_entry(',helper+'static PyObject *triangle_support_entry(',1)
begin=s.index('static PyObject *surface_ray_hits(');end=s.index('/* 胎冠高度',begin)
block=s[begin:end]
block=block.replace('double start[3],end[3],origin[3];','double start[3],end[3],origin[3],axis[3];',1)
block=block.replace('!vector(origin_object,origin))','!vector(origin_object,origin) || !vector(axis_object,axis))',1)
marker='        offset_object=Py_BuildValue('
pos=block.index(marker)
new='''        transform_values(start,axes,offset,0,local_start);
        transform_values(end,axes,offset,0,local_end);
        if (triangles!=Py_None) {
            double local_axis[3],zero[3]={0.},padding[3];
            transform_values(axis,axes,zero,0,local_axis);
            double shape_margin=PyFloat_AsDouble(margin);
            if (PyErr_Occurred() || !triangle_support_padding(local_axis,radius,width,shoulder,crown,shape_margin,padding)) goto failure;
            PyObject *center=PyObject_GetAttrString(triangles,"center"),*half_box=PyObject_GetAttrString(triangles,"half");
            if (!center || !half_box) { Py_XDECREF(center); Py_XDECREF(half_box); goto failure; }
            int possible=triangle_query_possible(center,half_box,local_start,local_end,padding);
            Py_DECREF(center); Py_DECREF(half_box);
            if (possible<0) goto failure;
            if (!possible) continue;
        }
'''
block=block[:pos]+new+block[pos:]
later=block.index('        if (!surface) goto failure;')
cut=block[later:]
cut=cut.replace('        transform_values(start,axes,offset,0,local_start);\n        transform_values(end,axes,offset,0,local_end);\n','',1)
block=block[:later]+cut;s=s[:begin]+block+s[end:]
p.write_text(s,encoding='utf-8')
