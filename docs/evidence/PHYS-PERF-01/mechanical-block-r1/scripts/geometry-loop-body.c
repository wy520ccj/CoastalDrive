static PyObject *box_interval_call(PyObject *self, PyObject *args, PyObject *kwargs) {
    PyObject *start_object, *end_object, *half_object;
    static char *names[] = {"start", "end", "half", NULL};
    if (!PyArg_ParseTupleAndKeywords(args,kwargs,"OOO",names,&start_object,&end_object,&half_object)) return NULL;
    double start[3],end[3],half[3];
    if (!vector(start_object,start) || !vector(end_object,end) || !vector(half_object,half)) return NULL;
    double entry=-INFINITY,exit_time=INFINITY,sign=0.;
    int normal_axis=-1;
    for (int a=0; a<3; ++a) {
        double speed=end[a]-start[a];
        if (speed == 0.) {
            if (fabs(start[a]) > half[a]) Py_RETURN_NONE;
            continue;
        }
        double near=(-half[a]-start[a])/speed,far=(half[a]-start[a])/speed;
        if (near > far) { double swap=near; near=far; far=swap; }
        if (near > entry) { entry=near; normal_axis=a; sign=speed>0. ? -1. : 1.; }
        if (far < exit_time) exit_time=far;
        if (entry > exit_time) Py_RETURN_NONE;
    }
    PyObject *normal=normal_axis < 0 ? Py_NewRef(Py_None) : Py_BuildValue("(ddd)",
        normal_axis==0 ? sign : 0.,normal_axis==1 ? sign : 0.,normal_axis==2 ? sign : 0.);
    if (!normal) return NULL;
    PyObject *result=Py_BuildValue("(ddO)",entry,exit_time,normal);
    Py_DECREF(normal);
    return result;
}

static PyObject *rotated_path_call(PyObject *self, PyObject *args, PyObject *kwargs) {
    PyObject *value_object,*axis_object;
    double angle,scale;
    static char *names[] = {"vector", "axis", "angle", "scale", NULL};
    if (!PyArg_ParseTupleAndKeywords(args,kwargs,"OOdd",names,&value_object,&axis_object,&angle,&scale)) return NULL;
    if (angle == 0.) return Py_BuildValue("(OO)",value_object,value_object);
    double value[3],axis[3];
    if (!vector(value_object,value) || !vector(axis_object,axis)) return NULL;
    double projection=dot(value,axis),parallel[3],radial[3],tangent[3],end[3],average[3];
    for (int a=0; a<3; ++a) { parallel[a]=projection*axis[a]; radial[a]=value[a]-parallel[a]; }
    tangent[0]=axis[1]*value[2]-axis[2]*value[1];
    tangent[1]=axis[2]*value[0]-axis[0]*value[2];
    tangent[2]=axis[0]*value[1]-axis[1]*value[0];
    double sine=sin(angle),cosine=cos(angle),average_sine=sine/angle;
    double average_cosine=2*pow(sin(angle/2),2)/angle;
    for (int a=0; a<3; ++a) {
        end[a]=parallel[a]+cosine*radial[a]+sine*tangent[a];
        average[a]=scale*(parallel[a]+average_sine*radial[a]+average_cosine*tangent[a]);
    }
    return Py_BuildValue("((ddd)(ddd))",end[0],end[1],end[2],average[0],average[1],average[2]);
}
