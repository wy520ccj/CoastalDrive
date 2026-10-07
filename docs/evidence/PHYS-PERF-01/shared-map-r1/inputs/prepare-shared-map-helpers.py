from pathlib import Path
p=Path('src/mechanical_kernels.c');s=p.read_text(encoding='utf-8')
start=s.index('        double rhs[3] =',s.index('static PyObject *shaft_state('));end=s.index('        return Py_BuildValue',start);body=s[start:end].replace('continue;','return 0;')
helper='''/* 同一分区判据供既有端口入口与共同状态映射使用。 */
static int shaft_trial(const double free_values[4],const double response[4][4],double dt,
                       double capacity,double brake_capacity,double efficiency,
                       double gear_free,const double reduced[3],const double modes[3],
                       double sign,double slope,const double columns[3][3],
                       double result[4],double end_speeds[4]) {
    const int ports[3]={0,2,3};
    const double tolerance=PORT_TOLERANCE;
'''+body+'''    for (int i=0; i<4; ++i) { result[i]=values[i]; end_speeds[i]=speeds[i]; }
    return 1;
}

'''
pos=s.index('static PyObject *shaft_state(');s=s[:pos]+helper+s[pos:];start=s.index(body.replace('return 0;','continue;'),s.index('static PyObject *shaft_state('));end=start+len(body);s=s[:start]+'''        double values[4],speeds[4];
        if (!shaft_trial(free_values,response,dt,capacity,brake_capacity,efficiency,
                         gear_free,reduced,modes,sign,slope,columns,values,speeds)) continue;
'''+s[end:];s=s.replace('return Py_BuildValue("((dddd)(dddd)n)", clutch, gear, loss, brake,','return Py_BuildValue("((dddd)(dddd)n)", values[0], values[1], values[2], values[3],',1);s=s.replace('    const double tolerance = PORT_TOLERANCE;\n    double gear_free', '    double gear_free',1)
# 数值组合只保留一份：接口解析与共同映射共用此函数。
start=s.index('    for (int a=0; a<3; ++a) input[a]=gyro[a];',s.index('static PyObject *known_result('));end=s.index('    PyObject *free=PyTuple_New(data->dimensions);',start)
helper='''static void known_values(const MassCoefficients *data,const double base[9],const double gyro[3],
                         const double angular[9],const double *normal,double dt,const double *road,
                         double values[9]) {
    double input[9]={0.},response[9];
    for (int a=0; a<3; ++a) input[a]=gyro[a];
    mass_response_values(data,input,response);
    for (int a=0; a<data->dimensions; ++a) values[a]=base[a]+dt*response[a]+angular[a];
    if (road) {
        for (int a=0; a<3; ++a) input[a]=0.;
        for (int a=0; a<4; ++a) input[a+data->wheel_start]=-road[a];
        mass_response_values(data,input,response);
        for (int a=0; a<data->dimensions; ++a) values[a]=values[a]+dt*response[a];
    }
    if (normal) for (int a=0; a<data->dimensions; ++a) values[a]=values[a]+normal[a];
}

'''
replacement='''    double torques[4];
    if (road!=Py_None && !vector(road,torques,4)) return NULL;
    PyObject *normal_object=PyTuple_GET_ITEM(loads,1);
    if (!PyTuple_Check(normal_object)) {
        PyErr_SetString(PyExc_ValueError,"法向载荷须为元组"); return NULL;
    }
    int suspension=PyTuple_GET_SIZE(normal_object)!=0;
    if (suspension && !vector(normal_object,normal,data->dimensions)) return NULL;
    known_values(data,base,gyro,angular,suspension ? normal : NULL,dt,
                 road!=Py_None ? torques : NULL,values);
'''
s=s[:start]+replacement+s[end:];s=s.replace('double base[9],angular[9],normal[9],input[9]={0.},response[9],values[9];','double base[9],angular[9],normal[9],values[9];',1);pos=s.index('/* 自由状态按原先后次序');s=s[:pos]+helper+s[pos:]
p.write_text(s,encoding='utf-8')
