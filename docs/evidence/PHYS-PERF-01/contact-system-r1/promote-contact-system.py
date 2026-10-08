"""提取原端点数值函数，四轮共用原运算与真实支持面回调。"""
from pathlib import Path

root = Path.cwd()
p = root / 'src/wheel_contact_kernels.c'
s = p.read_text(encoding='utf-8')
start = s.index('static PyObject *cylinder_endpoint(PyObject *self,PyObject *args) {')
parse_end = s.index('    PyObject *surface=PyObject_GetAttrString(contact,"surface")', start)
wrapper = s[start:parse_end]
helper = '''static PyObject *cylinder_endpoint_values(PyObject *contact,
    double hub_end[3],double hub_average[3],double direction_end[3],double direction_average[3],
    double rotation_axis[3],double angle,double scale,double velocity[3],double angular[3],double dt,
    PyObject *hub_average_object,PyObject *direction_average_object,PyObject *rotation_axis_object,
    PyObject *velocity_object,PyObject *angular_object,PyObject *face_difference) {
    PyObject *owned_hub_average=NULL,*owned_direction_average=NULL;
'''
s = s[:start] + helper + s[parse_end:]
callback = '                difference_object=PyObject_CallFunction(face_difference,'
position = s.index(callback, start)
s = s[:position] + '''                if (!hub_average_object) {
                    owned_hub_average=Py_BuildValue("(ddd)",hub_average[0],hub_average[1],hub_average[2]);
                    if (!owned_hub_average) goto failure;
                    hub_average_object=owned_hub_average;
                }
                if (!direction_average_object) {
                    owned_direction_average=Py_BuildValue("(ddd)",direction_average[0],direction_average[1],direction_average[2]);
                    if (!owned_direction_average) goto failure;
                    direction_average_object=owned_direction_average;
                }
''' + s[position:]
end = s.index('\nstatic PyMethodDef methods[]', start)
body = s[start:end]
body = body.replace('    Py_XDECREF(difference_object);',
    '    Py_XDECREF(owned_hub_average); Py_XDECREF(owned_direction_average);\n    Py_XDECREF(difference_object);')
body = body.replace('no_contact:\n',
    'no_contact:\n    Py_XDECREF(owned_hub_average); Py_XDECREF(owned_direction_average);\n')
wrapper += '''    return cylinder_endpoint_values(contact,hub_end,hub_average,direction_end,direction_average,
        rotation_axis,angle,scale,velocity,angular,dt,hub_average_object,direction_average_object,
        rotation_axis_object,velocity_object,angular_object,face_difference);
}

/* 四轮共用有限转动与接点装配；每个支持面仍执行原relative_entry。 */
static PyObject *cylinder_contact_system(PyObject *self,PyObject *args) {
    PyObject *contacts,*axis_object,*velocity_object,*angular_object,*face_difference;
    double angle,scale,dt,axis[3],velocity[3],angular[3];
    if (!PyArg_ParseTuple(args,"OOddOOdO",&contacts,&axis_object,&angle,&scale,
        &velocity_object,&angular_object,&dt,&face_difference)) return NULL;
    if (!vector(axis_object,axis) || !vector(velocity_object,velocity) || !vector(angular_object,angular)) return NULL;
    Py_ssize_t count=PyTuple_Size(contacts);
    if (count<0) return NULL;
    PyObject *gradients=PyTuple_New(count),*alignment=PyTuple_New(count),*touching=PyTuple_New(count);
    if (!gradients || !alignment || !touching) goto failure;
    for (Py_ssize_t i=0; i<count; ++i) {
        PyObject *contact=PyTuple_GET_ITEM(contacts,i),*endpoint;
        if (contact==Py_None) { endpoint=Py_NewRef(Py_None); }
        else {
            double hub[3],direction[3],hub_end[3],hub_average[3],direction_end[3],direction_average[3];
            if (!vector_attribute(contact,"hub",hub) || !vector_attribute(contact,"direction",direction)) goto failure;
            rotated_path_values(hub,axis,angle,scale,hub_end,hub_average);
            rotated_path_values(direction,axis,angle,scale,direction_end,direction_average);
            endpoint=cylinder_endpoint_values(contact,hub_end,hub_average,direction_end,direction_average,
                axis,angle,scale,velocity,angular,dt,NULL,NULL,axis_object,velocity_object,angular_object,face_difference);
            if (!endpoint) goto failure;
        }
        if (endpoint==Py_None) {
            PyObject *zero=Py_BuildValue("(dddddd)",0.,0.,0.,0.,0.,0.);
            if (!zero) { Py_DECREF(endpoint); goto failure; }
            PyTuple_SET_ITEM(gradients,i,zero);
            PyTuple_SET_ITEM(alignment,i,Py_NewRef(Py_None));
            PyTuple_SET_ITEM(touching,i,Py_NewRef(Py_False));
        } else {
            PyTuple_SET_ITEM(gradients,i,Py_NewRef(PyTuple_GET_ITEM(endpoint,0)));
            PyTuple_SET_ITEM(alignment,i,Py_NewRef(PyTuple_GET_ITEM(endpoint,1)));
            PyTuple_SET_ITEM(touching,i,Py_NewRef(Py_True));
        }
        Py_DECREF(endpoint);
    }
    return Py_BuildValue("NNN",gradients,alignment,touching);
failure:
    Py_XDECREF(gradients); Py_XDECREF(alignment); Py_XDECREF(touching); return NULL;
}
'''
s = s[:start] + body + wrapper + s[end:]
s = s.replace('static PyMethodDef methods[] = {',
    'static PyMethodDef methods[] = {\n    {"cylinder_contact_system", (PyCFunction)cylinder_contact_system, METH_VARARGS, "原四轮有限接点几何与装配"},')
p.write_text(s, encoding='utf-8', newline='\n')
p=root/'src/suspension_kinematics.py'
s=p.read_text(encoding='utf-8')
s=s.replace('from wheel_contact_kernels import cylinder_endpoint as endpoint_kernel',
    'from wheel_contact_kernels import cylinder_contact_system\nfrom wheel_contact_kernels import cylinder_endpoint as endpoint_kernel')
s=s.replace('    gradients, alignment, touching = [], [], []', '''    if all(plane is None or isinstance(plane.surface, CylinderSurface) for plane in system.kinematics):
        gradients, alignment, touching = cylinder_contact_system(
            system.kinematics, axis, angle, scale, velocity, angular, dt, face_extension_difference)
        return replace(system, gradients=gradients, alignment=alignment, touching=touching)
    gradients, alignment, touching = [], [], []''',1)
p.write_text(s,encoding='utf-8',newline='\n')
