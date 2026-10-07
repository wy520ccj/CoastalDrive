/* 同一次共同求解的逆惯量和实体轴投影固定，只保存只读数值系数。 */
typedef struct {
    int dimensions,wheel_start,projection_count,has_drag;
    double inverse[9],engine_inertia,shaft_inertia,wheel_inertia,drag_factor;
    double gradients[3][9],responses[3][9],factors[3],engine_response[9];
} MassCoefficients;

static const char *mass_coefficients_name="CoastalDrive.mass_coefficients";

static void release_mass_coefficients(PyObject *object) {
    PyMem_Free(PyCapsule_GetPointer(object,mass_coefficients_name));
}

static PyObject *mass_coefficients_call(PyObject *self,PyObject *args,PyObject *kwargs) {
    PyObject *inverse,*shaft,*projections_object,*engine_response;
    double engine_inertia,wheel_inertia,drag_factor;
    static char *names[]={"inverse_inertia","engine_inertia","shaft_inertia","wheel_inertia",
                         "projections","drag_factor","engine_response",NULL};
    if (!PyArg_ParseTupleAndKeywords(args,kwargs,"OdOdOdO",names,&inverse,&engine_inertia,&shaft,&wheel_inertia,
                                     &projections_object,&drag_factor,&engine_response)) return NULL;
    MassCoefficients *data=PyMem_Calloc(1,sizeof(MassCoefficients));
    if (!data) return PyErr_NoMemory();
    data->dimensions=shaft == Py_None ? 8 : 9;
    data->wheel_start=shaft == Py_None ? 4 : 5;
    data->engine_inertia=engine_inertia;
    data->wheel_inertia=wheel_inertia;
    data->shaft_inertia=shaft == Py_None ? 1. : PyFloat_AsDouble(shaft);
    data->drag_factor=drag_factor;
    data->has_drag=engine_response != Py_None;
    if (PyErr_Occurred() || !matrix_values(inverse,data->inverse,3,3)
        || (data->has_drag && !vector(engine_response,data->engine_response,data->dimensions))) goto failed;
    if (data->engine_inertia == 0. || data->shaft_inertia == 0. || data->wheel_inertia == 0.) {
        PyErr_SetString(PyExc_ZeroDivisionError,"机械转子惯量为零"); goto failed;
    }
    PyObject *projections=PySequence_Fast(projections_object,"实体轴投影须为序列");
    if (!projections) goto failed;
    Py_ssize_t count=PySequence_Fast_GET_SIZE(projections);
    if (count>3) {
        Py_DECREF(projections); PyErr_SetString(PyExc_ValueError,"实体输出/前/后轴投影最多三组"); goto failed;
    }
    data->projection_count=(int)count;
    for (int i=0; i<data->projection_count; ++i) {
        PyObject *part=PySequence_Fast(PySequence_Fast_GET_ITEM(projections,i),"实体轴投影须为梯度/响应/系数");
        if (!part) { Py_DECREF(projections); goto failed; }
        if (PySequence_Fast_GET_SIZE(part)!=3) {
            Py_DECREF(part); Py_DECREF(projections); PyErr_SetString(PyExc_ValueError,"实体轴投影须为梯度/响应/系数"); goto failed;
        }
        int ok=vector(PySequence_Fast_GET_ITEM(part,0),data->gradients[i],data->dimensions)
            && vector(PySequence_Fast_GET_ITEM(part,1),data->responses[i],data->dimensions);
        data->factors[i]=PyFloat_AsDouble(PySequence_Fast_GET_ITEM(part,2));
        Py_DECREF(part);
        if (!ok || PyErr_Occurred()) { Py_DECREF(projections); goto failed; }
    }
    Py_DECREF(projections);
    PyObject *result=PyCapsule_New(data,mass_coefficients_name,release_mass_coefficients);
    if (!result) goto failed;
    return result;
failed:
    PyMem_Free(data); return NULL;
}

static PyObject *mass_response_prepared_call(PyObject *self,PyObject *args,PyObject *kwargs) {
    PyObject *coefficients,*input;
    static char *names[]={"coefficients","vector",NULL};
    if (!PyArg_ParseTupleAndKeywords(args,kwargs,"OO",names,&coefficients,&input)) return NULL;
    MassCoefficients *data=PyCapsule_GetPointer(coefficients,mass_coefficients_name);
    if (!data) return NULL;
    double source[9],values[9],terms[9];
    if (!vector(input,source,data->dimensions)) return NULL;
    for (int a=0; a<3; ++a) {
        for (int b=0; b<3; ++b) terms[b]=data->inverse[a*3+b]*source[b];
        values[a]=compensated(terms,3);
    }
    values[3]=source[3]/data->engine_inertia;
    if (data->wheel_start==5) values[4]=source[4]/data->shaft_inertia;
    for (int a=data->wheel_start; a<data->dimensions; ++a) values[a]=source[a]/data->wheel_inertia;
    for (int i=0; i<data->projection_count; ++i) {
        for (int a=0; a<data->dimensions; ++a) terms[a]=data->gradients[i][a]*values[a];
        double scale=data->factors[i]*compensated(terms,data->dimensions);
        for (int a=0; a<data->dimensions; ++a) values[a]=values[a]-scale*data->responses[i][a];
    }
    if (data->has_drag) {
        for (int a=0; a<data->dimensions; ++a) terms[a]=data->engine_response[a]*source[a];
        double projection=data->drag_factor*compensated(terms,data->dimensions);
        for (int a=0; a<data->dimensions; ++a) values[a]=values[a]-projection*data->engine_response[a];
    }
    PyObject *result=PyTuple_New(data->dimensions);
    if (!result) return NULL;
    for (int a=0; a<data->dimensions; ++a) {
        PyObject *value=PyFloat_FromDouble(values[a]);
        if (!value) { Py_DECREF(result); return NULL; }
        PyTuple_SET_ITEM(result,a,value);
    }
    return result;
}
