static int matrix_values(PyObject *object,double *values,int rows,int columns) {
    PyObject *sequence=PySequence_Fast(object,"机械矩阵须为行序列");
    if (!sequence) return 0;
    if (PySequence_Fast_GET_SIZE(sequence) != rows) {
        Py_DECREF(sequence); PyErr_SetString(PyExc_ValueError,"机械矩阵行数不一致"); return 0;
    }
    for (int i=0; i<rows; ++i) {
        if (!vector(PySequence_Fast_GET_ITEM(sequence,i),values+i*columns,columns)) { Py_DECREF(sequence); return 0; }
    }
    Py_DECREF(sequence); return 1;
}

static PyObject *rotor_spin_call(PyObject *self,PyObject *args,PyObject *kwargs) {
    PyObject *state_object,*engine_axis_object,*axes_object,*shaft_object,*shaft_axis_object;
    PyObject *inertia_object,*gradient_object,*downstream_axis_object;
    double engine_inertia,wheel_inertia;
    int rotor;
    static char *names[]={"state","engine_inertia","engine_axis","wheel_inertia","wheel_axes","rotor",
                         "shaft_inertia","shaft_axis","inertias","gradients","downstream_axes",NULL};
    if (!PyArg_ParseTupleAndKeywords(args,kwargs,"OdOdOpOOOOO",names,&state_object,&engine_inertia,&engine_axis_object,
                                    &wheel_inertia,&axes_object,&rotor,&shaft_object,&shaft_axis_object,
                                    &inertia_object,&gradient_object,&downstream_axis_object)) return NULL;
    int shaft=shaft_object != Py_None,dimensions=shaft ? 9 : 8,wheel_start=shaft ? 5 : 4;
    double state[9],engine_axis[3],axes[12],shaft_axis[3],terms[9],base[3],result[3];
    if (!vector(state_object,state,dimensions) || !vector(engine_axis_object,engine_axis,3)
        || !matrix_values(axes_object,axes,4,3)) return NULL;
    double shaft_inertia=shaft ? PyFloat_AsDouble(shaft_object) : 0.;
    if (PyErr_Occurred() || (shaft && !vector(shaft_axis_object,shaft_axis,3))) return NULL;
    for (int a=0; a<3; ++a) {
        for (int i=0; i<4; ++i) terms[i]=state[i+wheel_start]*axes[i*3+a];
        base[a]=engine_inertia*state[3]*engine_axis[a]-(rotor ? wheel_inertia*compensated(terms,4) : 0.)
                +(shaft ? shaft_inertia*state[4]*shaft_axis[a] : 0.);
    }
    PyObject *inertias=PySequence_Fast(inertia_object,"实体轴惯量须为序列");
    if (!inertias) return NULL;
    int downstream=PySequence_Fast_GET_SIZE(inertias) != 0;
    Py_DECREF(inertias);
    if (downstream) {
        double inertia[3],gradients[27],downstream_axes[9],momentum[3];
        if (!vector(inertia_object,inertia,3) || !matrix_values(gradient_object,gradients,3,dimensions)
            || !matrix_values(downstream_axis_object,downstream_axes,3,3)) return NULL;
        for (int i=0; i<3; ++i) {
            for (int b=0; b<dimensions; ++b) terms[b]=gradients[i*dimensions+b]*state[b];
            momentum[i]=inertia[i]*compensated(terms,dimensions);
        }
        for (int a=0; a<3; ++a) {
            for (int i=0; i<3; ++i) terms[i]=momentum[i]*downstream_axes[i*3+a];
            result[a]=base[a]+compensated(terms,3);
        }
    } else {
        for (int a=0; a<3; ++a) result[a]=base[a];
    }
    return Py_BuildValue("(ddd)",result[0],result[1],result[2]);
}
