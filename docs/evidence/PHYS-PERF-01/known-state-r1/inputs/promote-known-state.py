from pathlib import Path
root=Path.cwd();p=root/'src/mechanical_kernels.c';s=p.read_text(encoding='utf-8')
start=s.index('    for (int a=0; a<3; ++a) {',s.index('static PyObject *mass_response_prepared_call('));end=s.index('    PyObject *result=PyTuple_New(data->dimensions);',start)
body=s[start:end]
helper='static void mass_response_values(const MassCoefficients *data, const double source[9], double values[9]) {\n    double terms[9];\n'+body+'}\n\n'
insert=s.index('static PyObject *mass_response_prepared_call(');s=s[:insert]+helper+s[insert:];start=s.index(body,s.index('static PyObject *mass_response_prepared_call('));s=s[:start]+'    mass_response_values(data,source,values);\n'+s[start+len(body):];s=s.replace('double source[9],values[9],terms[9];','double source[9],values[9];',1)
start=s.index('    for (int a=0; a<3; ++a) {',s.index('static PyObject *rotor_spin_prepared_call('));end=s.index('    return Py_BuildValue("(ddd)"',start);body=s[start:end]
helper='static void rotor_spin_values(const RotorCoefficients *data, const double state[9], double result[3]) {\n    double terms[9],base[3];\n'+body+'}\n\n';insert=s.index('static PyObject *rotor_spin_prepared_call(');s=s[:insert]+helper+s[insert:];start=s.index(body,s.index('static PyObject *rotor_spin_prepared_call('));s=s[:start]+'    rotor_spin_values(data,state,result);\n'+s[start+len(body):];s=s.replace('double state[9],terms[9],base[3],result[3];','double state[9],result[3];',1)
block=r'''
/* 自由状态按原先后次序叠加陀螺、轮端、滚阻及当前法向载荷。 */
static PyObject *known_result(const MassCoefficients *data, PyObject *base_object,
                              const double gyro[3], PyObject *loads, double dt, PyObject *road) {
    double base[9],angular[9],normal[9],input[9]={0.},response[9],values[9];
    if (!PyTuple_Check(loads) || PyTuple_GET_SIZE(loads)!=3) {
        PyErr_SetString(PyExc_ValueError,"共同载荷须含角向、法向及平动自由速度"); return NULL;
    }
    if (!vector(base_object,base,data->dimensions)
        || !vector(PyTuple_GET_ITEM(loads,0),angular,data->dimensions)) return NULL;
    for (int a=0; a<3; ++a) input[a]=gyro[a];
    mass_response_values(data,input,response);
    for (int a=0; a<data->dimensions; ++a) values[a]=base[a]+dt*response[a]+angular[a];
    if (road!=Py_None) {
        double torques[4];
        if (!vector(road,torques,4)) return NULL;
        for (int a=0; a<3; ++a) input[a]=0.;
        for (int a=0; a<4; ++a) input[a+data->wheel_start]=-torques[a];
        mass_response_values(data,input,response);
        for (int a=0; a<data->dimensions; ++a) values[a]=values[a]+dt*response[a];
    }
    PyObject *normal_object=PyTuple_GET_ITEM(loads,1);
    if (!PyTuple_Check(normal_object)) {
        PyErr_SetString(PyExc_ValueError,"法向载荷须为元组"); return NULL;
    }
    if (PyTuple_GET_SIZE(normal_object)) {
        if (!vector(normal_object,normal,data->dimensions)) return NULL;
        for (int a=0; a<data->dimensions; ++a) values[a]=values[a]+normal[a];
    }
    PyObject *free=PyTuple_New(data->dimensions);
    if (!free) return NULL;
    for (int a=0; a<data->dimensions; ++a) {
        PyObject *value=PyFloat_FromDouble(values[a]);
        if (!value) { Py_DECREF(free); return NULL; }
        PyTuple_SET_ITEM(free,a,value);
    }
    return Py_BuildValue("(NO)",free,PyTuple_GET_ITEM(loads,2));
}

static PyObject *known_state_call(PyObject *self,PyObject *args,PyObject *kwargs) {
    PyObject *coefficients,*base,*input,*loads,*road;
    double dt,gyro[3];
    static char *names[]={"coefficients","free_base","gyro","loads","dt","road_torques",NULL};
    if (!PyArg_ParseTupleAndKeywords(args,kwargs,"OOOOdO",names,&coefficients,&base,&input,&loads,&dt,&road)) return NULL;
    MassCoefficients *data=PyCapsule_GetPointer(coefficients,mass_coefficients_name);
    if (!data || !vector(input,gyro,3)) return NULL;
    return known_result(data,base,gyro,loads,dt,road);
}

static PyObject *rotor_known_state_call(PyObject *self,PyObject *args,PyObject *kwargs) {
    PyObject *coefficients,*spin_coefficients,*base,*input,*loads,*road;
    double dt;
    static char *names[]={"coefficients","rotor_coefficients","free_base","state","loads","dt","road_torques",NULL};
    if (!PyArg_ParseTupleAndKeywords(args,kwargs,"OOOOOdO",names,&coefficients,&spin_coefficients,
                                     &base,&input,&loads,&dt,&road)) return NULL;
    MassCoefficients *data=PyCapsule_GetPointer(coefficients,mass_coefficients_name);
    RotorCoefficients *spin=PyCapsule_GetPointer(spin_coefficients,rotor_coefficients_name);
    if (!data || !spin) return NULL;
    if (data->dimensions!=spin->dimensions) {
        PyErr_SetString(PyExc_ValueError,"共同自由状态与转子维数不一致"); return NULL;
    }
    double state[9],momentum[3],gyro[3];
    if (!vector(input,state,data->dimensions)) return NULL;
    rotor_spin_values(spin,state,momentum);
    gyro[0]=momentum[1]*state[2]-momentum[2]*state[1];
    gyro[1]=momentum[2]*state[0]-momentum[0]*state[2];
    gyro[2]=momentum[0]*state[1]-momentum[1]*state[0];
    return known_result(data,base,gyro,loads,dt,road);
}
'''
pos=s.index('static PyObject *rotor_spin_call(');s=s[:pos]+block+'\n'+s[pos:];s=s.replace('static PyMethodDef methods[] = {','static PyMethodDef methods[] = {\n    {"known_state", (PyCFunction)known_state_call, METH_VARARGS | METH_KEYWORDS, "原共同自由速度与当前载荷组合"},\n    {"rotor_known_state", (PyCFunction)rotor_known_state_call, METH_VARARGS | METH_KEYWORDS, "原转子陀螺与共同自由速度组合"},',1);p.write_text(s,encoding='utf-8')
p=root/'src/tire_drivetrain.py';s=p.read_text(encoding='utf-8');s=s.replace('    dot,','    dot,\n    known_state,',1).replace('    rotor_coefficients,','    rotor_coefficients,\n    rotor_known_state,',1)
start=s.index('    def known(gyro, loads):');end=s.index('    spin_columns = None',start);s=s[:start]+'''    def known(gyro, loads):
        return known_state(mobility_coefficients, free_base, gyro, loads, dt,
                           road_torques if rolling_active else None)

'''+s[end:]
s=s.replace('            free, end_velocity = known(cross(spin(state), state[:3]), loads)','            free, end_velocity = rotor_known_state(mobility_coefficients, spin_coefficients, free_base,\n                state[:dimensions], loads, dt, road_torques if rolling_active else None)',1);p.write_text(s,encoding='utf-8')
