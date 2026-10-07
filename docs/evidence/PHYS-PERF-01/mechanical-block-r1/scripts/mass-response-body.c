static int project_response_data(double *values,int dimensions,PyObject *projection_object) {
    PyObject *projections=PySequence_Fast(projection_object,"机械投影须为序列");
    if (!projections) return 0;
    for (Py_ssize_t k=0; k<PySequence_Fast_GET_SIZE(projections); ++k) {
        PyObject *part=PySequence_Fast(PySequence_Fast_GET_ITEM(projections,k),"机械投影须为梯度/响应/系数");
        if (!part) { Py_DECREF(projections); return 0; }
        if (PySequence_Fast_GET_SIZE(part) != 3) {
            Py_DECREF(part); Py_DECREF(projections);
            PyErr_SetString(PyExc_ValueError,"机械投影须为梯度/响应/系数"); return 0;
        }
        double gradient[9],response[9],terms[9];
        int ok=vector(PySequence_Fast_GET_ITEM(part,0),gradient,dimensions)
            && vector(PySequence_Fast_GET_ITEM(part,1),response,dimensions);
        double factor=PyFloat_AsDouble(PySequence_Fast_GET_ITEM(part,2));
        Py_DECREF(part);
        if (!ok || PyErr_Occurred()) { Py_DECREF(projections); return 0; }
        for (int i=0; i<dimensions; ++i) terms[i]=gradient[i]*values[i];
        double scale=factor*compensated(terms,dimensions);
        for (int i=0; i<dimensions; ++i) values[i]=values[i]-scale*response[i];
    }
    Py_DECREF(projections); return 1;
}

static PyObject *mass_response_call(PyObject *self,PyObject *args,PyObject *kwargs) {
    PyObject *input,*inertia_object,*shaft_object,*projections,*engine_response_object;
    double engine_inertia,wheel_inertia,drag_factor;
    static char *names[]={"vector","inverse_inertia","engine_inertia","shaft_inertia","wheel_inertia",
                         "projections","drag_factor","engine_response",NULL};
    if (!PyArg_ParseTupleAndKeywords(args,kwargs,"OOdOdOdO",names,&input,&inertia_object,&engine_inertia,
                                     &shaft_object,&wheel_inertia,&projections,&drag_factor,&engine_response_object)) return NULL;
    int shaft=shaft_object != Py_None,dimensions=shaft ? 9 : 8,wheel_start=shaft ? 5 : 4;
    double source[9],values[9],terms[9],engine_response[9];
    if (!vector(input,source,dimensions)) return NULL;
    double shaft_inertia=shaft ? PyFloat_AsDouble(shaft_object) : 1.;
    if (PyErr_Occurred()) return NULL;
    if (engine_inertia == 0. || wheel_inertia == 0. || shaft_inertia == 0.) {
        PyErr_SetString(PyExc_ZeroDivisionError,"机械转子惯量为零"); return NULL;
    }
    PyObject *rows=PySequence_Fast(inertia_object,"逆惯量须为三行矩阵");
    if (!rows) return NULL;
    if (PySequence_Fast_GET_SIZE(rows) != 3) {
        Py_DECREF(rows); PyErr_SetString(PyExc_ValueError,"逆惯量须为三行矩阵"); return NULL;
    }
    for (int a=0; a<3; ++a) {
        double row[3];
        if (!vector(PySequence_Fast_GET_ITEM(rows,a),row,3)) { Py_DECREF(rows); return NULL; }
        for (int b=0; b<3; ++b) terms[b]=row[b]*source[b];
        values[a]=compensated(terms,3);
    }
    Py_DECREF(rows);
    values[3]=source[3]/engine_inertia;
    if (shaft) values[4]=source[4]/shaft_inertia;
    for (int a=wheel_start; a<dimensions; ++a) values[a]=source[a]/wheel_inertia;
    if (!project_response_data(values,dimensions,projections)) return NULL;
    if (engine_response_object != Py_None) {
        if (!vector(engine_response_object,engine_response,dimensions)) return NULL;
        for (int a=0; a<dimensions; ++a) terms[a]=engine_response[a]*source[a];
        double projection=drag_factor*compensated(terms,dimensions);
        for (int a=0; a<dimensions; ++a) values[a]=values[a]-projection*engine_response[a];
    }
    PyObject *result=PyTuple_New(dimensions);
    if (!result) return NULL;
    for (int a=0; a<dimensions; ++a) {
        PyObject *value=PyFloat_FromDouble(values[a]);
        if (!value) { Py_DECREF(result); return NULL; }
        PyTuple_SET_ITEM(result,a,value);
    }
    return result;
}
