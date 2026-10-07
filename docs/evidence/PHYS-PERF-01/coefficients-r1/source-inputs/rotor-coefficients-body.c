typedef struct {
    int dimensions,wheel_start,rotor,shaft,downstream;
    double engine_inertia,wheel_inertia,shaft_inertia;
    double engine_axis[3],wheel_axes[12],shaft_axis[3],inertias[3],gradients[27],downstream_axes[9];
} RotorCoefficients;

static const char *rotor_coefficients_name="CoastalDrive.rotor_coefficients";

static void release_rotor_coefficients(PyObject *object) {
    PyMem_Free(PyCapsule_GetPointer(object,rotor_coefficients_name));
}

static PyObject *rotor_coefficients_call(PyObject *self,PyObject *args,PyObject *kwargs) {
    PyObject *engine_axis,*axes,*shaft,*shaft_axis,*inertias,*gradients,*downstream_axes;
    double engine_inertia,wheel_inertia;
    int rotor;
    static char *names[]={"engine_inertia","engine_axis","wheel_inertia","wheel_axes","rotor",
                         "shaft_inertia","shaft_axis","inertias","gradients","downstream_axes",NULL};
    if (!PyArg_ParseTupleAndKeywords(args,kwargs,"dOdOpOOOOO",names,&engine_inertia,&engine_axis,&wheel_inertia,
                                     &axes,&rotor,&shaft,&shaft_axis,&inertias,&gradients,&downstream_axes)) return NULL;
    RotorCoefficients *data=PyMem_Calloc(1,sizeof(RotorCoefficients));
    if (!data) return PyErr_NoMemory();
    data->rotor=rotor; data->shaft=shaft != Py_None;
    data->dimensions=data->shaft ? 9 : 8; data->wheel_start=data->shaft ? 5 : 4;
    data->engine_inertia=engine_inertia; data->wheel_inertia=wheel_inertia;
    data->shaft_inertia=data->shaft ? PyFloat_AsDouble(shaft) : 0.;
    if (PyErr_Occurred() || !vector(engine_axis,data->engine_axis,3) || !matrix_values(axes,data->wheel_axes,4,3)
        || (data->shaft && !vector(shaft_axis,data->shaft_axis,3))) goto failed;
    PyObject *sequence=PySequence_Fast(inertias,"实体轴惯量须为序列");
    if (!sequence) goto failed;
    data->downstream=PySequence_Fast_GET_SIZE(sequence) != 0;
    Py_DECREF(sequence);
    if (data->downstream && (!vector(inertias,data->inertias,3)
        || !matrix_values(gradients,data->gradients,3,data->dimensions)
        || !matrix_values(downstream_axes,data->downstream_axes,3,3))) goto failed;
    PyObject *result=PyCapsule_New(data,rotor_coefficients_name,release_rotor_coefficients);
    if (!result) goto failed;
    return result;
failed:
    PyMem_Free(data); return NULL;
}

static PyObject *rotor_spin_prepared_call(PyObject *self,PyObject *args,PyObject *kwargs) {
    PyObject *coefficients,*input;
    static char *names[]={"coefficients","state",NULL};
    if (!PyArg_ParseTupleAndKeywords(args,kwargs,"OO",names,&coefficients,&input)) return NULL;
    RotorCoefficients *data=PyCapsule_GetPointer(coefficients,rotor_coefficients_name);
    if (!data) return NULL;
    double state[9],terms[9],base[3],result[3];
    if (!vector(input,state,data->dimensions)) return NULL;
    for (int a=0; a<3; ++a) {
        for (int i=0; i<4; ++i) terms[i]=state[i+data->wheel_start]*data->wheel_axes[i*3+a];
        base[a]=data->engine_inertia*state[3]*data->engine_axis[a]
            -(data->rotor ? data->wheel_inertia*compensated(terms,4) : 0.)
            +(data->shaft ? data->shaft_inertia*state[4]*data->shaft_axis[a] : 0.);
    }
    if (data->downstream) {
        double momentum[3];
        for (int i=0; i<3; ++i) {
            for (int b=0; b<data->dimensions; ++b) terms[b]=data->gradients[i*data->dimensions+b]*state[b];
            momentum[i]=data->inertias[i]*compensated(terms,data->dimensions);
        }
        for (int a=0; a<3; ++a) {
            for (int i=0; i<3; ++i) terms[i]=momentum[i]*data->downstream_axes[i*3+a];
            result[a]=base[a]+compensated(terms,3);
        }
    } else {
        for (int a=0; a<3; ++a) result[a]=base[a];
    }
    return Py_BuildValue("(ddd)",result[0],result[1],result[2]);
}

static PyObject *rotor_spin_call(PyObject *self,PyObject *args,PyObject *kwargs) {
    PyObject *state,*engine_axis,*axes,*shaft,*shaft_axis,*inertias,*gradients,*downstream_axes;
    double engine_inertia,wheel_inertia;
    int rotor;
    static char *names[]={"state","engine_inertia","engine_axis","wheel_inertia","wheel_axes","rotor",
                         "shaft_inertia","shaft_axis","inertias","gradients","downstream_axes",NULL};
    if (!PyArg_ParseTupleAndKeywords(args,kwargs,"OdOdOpOOOOO",names,&state,&engine_inertia,&engine_axis,&wheel_inertia,
                                     &axes,&rotor,&shaft,&shaft_axis,&inertias,&gradients,&downstream_axes)) return NULL;
    PyObject *parameters=Py_BuildValue("(dOdOiOOOOO)",engine_inertia,engine_axis,wheel_inertia,axes,rotor,
                                      shaft,shaft_axis,inertias,gradients,downstream_axes);
    if (!parameters) return NULL;
    PyObject *coefficients=rotor_coefficients_call(self,parameters,NULL);
    Py_DECREF(parameters);
    if (!coefficients) return NULL;
    parameters=PyTuple_Pack(2,coefficients,state);
    Py_DECREF(coefficients);
    if (!parameters) return NULL;
    PyObject *result=rotor_spin_prepared_call(self,parameters,NULL);
    Py_DECREF(parameters);
    return result;
}
