from pathlib import Path
p=Path('src/wheel_contact_kernels.c');s=p.read_text(encoding='utf-8')
start=s.index('    double ab[3], ac[3], normal[3]',s.index('static PyObject *triangle_face('));end=s.index('\nstatic double exact_dot(',start);body=s[start:end]
helper='''/* 既有单面入口与整条查询共用原有限面判据。 */
static PyObject *triangle_face_values(double start[3],double end[3],double vertices[3][3],
    double margin,double axis[3],double radius,double width,double shoulder,double crown,
    int face_only,double ceiling) {
'''+body+'\n'
s=s[:start]+'''    return triangle_face_values(start,end,vertices,margin,axis,radius,width,shoulder,crown,face_only,ceiling);
}
'''+s[end:];pos=s.index('static PyObject *triangle_face(');s=s[:pos]+helper+s[pos:]
start=s.index('    double entry=-INFINITY,exit_time=INFINITY,sign=0.;',s.index('static PyObject *box_interval_call('));end=s.index('    PyObject *normal=normal_axis',start)
body=s[start:end].replace('Py_RETURN_NONE;','return 0;')
helper='''static int box_interval_values(double start[3],double end[3],double half[3],
    double *entry_out,double *exit_out,int *axis_out,double *sign_out) {
'''+body+'''    *entry_out=entry; *exit_out=exit_time; *axis_out=normal_axis; *sign_out=sign;
    return 1;
}

'''
s=s[:start]+'''    double entry,exit_time,sign;
    int normal_axis;
    if (!box_interval_values(start,end,half,&entry,&exit_time,&normal_axis,&sign)) Py_RETURN_NONE;
'''+s[end:];pos=s.index('static PyObject *box_interval_call(');s=s[:pos]+helper+s[pos:]
p.write_text(s,encoding='utf-8')
