typedef struct {
    int dimensions;
    double dt,mass,responses[108],tangents[12],axles[12];
} LoadCoefficients;

static const char *load_coefficients_name="CoastalDrive.load_coefficients";

static void release_load_coefficients(PyObject *object) {
    PyMem_Free(PyCapsule_GetPointer(object,load_coefficients_name));
}

static PyObject *load_coefficients_call(PyObject *self,PyObject *args,PyObject *kwargs) {
    PyObject *responses,*tangents,*axles;
    double dt,mass;
    int dimensions;
    static char *names[]={"responses","tangents","axles","dt","mass","dimensions",NULL};
    if (!PyArg_ParseTupleAndKeywords(args,kwargs,"OOOddi",names,&responses,&tangents,&axles,&dt,&mass,&dimensions)) return NULL;
    if (dimensions!=8 && dimensions!=9) { PyErr_SetString(PyExc_ValueError,"机械状态须为八或九维"); return NULL; }
    if (mass==0.) { PyErr_SetString(PyExc_ZeroDivisionError,"机械车身质量为零"); return NULL; }
    LoadCoefficients *data=PyMem_Calloc(1,sizeof(LoadCoefficients));
    if (!data) return PyErr_NoMemory();
    data->dimensions=dimensions; data->dt=dt; data->mass=mass;
    if (!matrix_values(tangents,data->tangents,4,3) || !matrix_values(axles,data->axles,4,3)) goto failed;
    PyObject *wheels=PySequence_Fast(responses,"轮端响应须为四轮序列");
    if (!wheels) goto failed;
    if (PySequence_Fast_GET_SIZE(wheels)!=4) {
        Py_DECREF(wheels); PyErr_SetString(PyExc_ValueError,"轮端响应须为四轮序列"); goto failed;
    }
    for (int i=0; i<4; ++i) {
        if (!matrix_values(PySequence_Fast_GET_ITEM(wheels,i),data->responses+i*3*dimensions,3,dimensions)) {
            Py_DECREF(wheels); goto failed;
        }
    }
    Py_DECREF(wheels);
    PyObject *result=PyCapsule_New(data,load_coefficients_name,release_load_coefficients);
    if (!result) goto failed;
    return result;
failed:
    PyMem_Free(data); return NULL;
}

static PyObject *wheel_load_prepared_call(PyObject *self,PyObject *args,PyObject *kwargs) {
    PyObject *coefficients,*forces,*velocity_object,*normal_forces_object,*normal_responses_object,*gradients_object,*exclude_object;
    static char *names[]={"coefficients","forces","velocity","normal_forces","normal_responses","normal_gradients","exclude",NULL};
    if (!PyArg_ParseTupleAndKeywords(args,kwargs,"OOOOOOO",names,&coefficients,&forces,&velocity_object,&normal_forces_object,
                                     &normal_responses_object,&gradients_object,&exclude_object)) return NULL;
    LoadCoefficients *data=PyCapsule_GetPointer(coefficients,load_coefficients_name);
    if (!data) return NULL;
    double force[12],velocity[3],end_velocity[3],terms[4],angular[9],normal[9];
    if (!matrix_values(forces,force,4,3) || !vector(velocity_object,velocity,3)) return NULL;
    long exclude=exclude_object==Py_None ? -1 : PyLong_AsLong(exclude_object);
    if (PyErr_Occurred()) return NULL;
    for (int a=0; a<data->dimensions; ++a) {
        int count=0;
        for (int i=0; i<4; ++i) {
            if (i==exclude) continue;
            terms[count++]=force[i*3]*data->responses[(i*3)*data->dimensions+a]
                +force[i*3+1]*data->responses[(i*3+1)*data->dimensions+a]
                -force[i*3+2]*data->responses[(i*3+2)*data->dimensions+a];
        }
        angular[a]=data->dt*compensated(terms,count);
    }
    /* 平动自由速度每次从真实调用输入读取，不属于固定轮端系数。 */
    for (int a=0; a<3; ++a) {
        int count=0;
        for (int i=0; i<4; ++i) {
            if (i!=exclude) terms[count++]=force[i*3]*data->tangents[i*3+a]+force[i*3+1]*data->axles[i*3+a];
        }
        end_velocity[a]=velocity[a]+data->dt/data->mass*compensated(terms,count);
    }
    int suspension=normal_forces_object!=Py_None;
    if (suspension) {
        double normal_forces[4],normal_responses[36],gradients[24];
        if (!vector(normal_forces_object,normal_forces,4)
            || !matrix_values(normal_responses_object,normal_responses,4,data->dimensions)
            || !matrix_values(gradients_object,gradients,4,6)) return NULL;
        for (int a=0; a<data->dimensions; ++a) {
            for (int i=0; i<4; ++i) terms[i]=normal_forces[i]*normal_responses[i*data->dimensions+a];
            normal[a]=data->dt*compensated(terms,4);
        }
        for (int a=0; a<3; ++a) {
            for (int i=0; i<4; ++i) terms[i]=normal_forces[i]*gradients[i*6+a];
            end_velocity[a]=end_velocity[a]+data->dt/data->mass*compensated(terms,4);
        }
    }
    PyObject *angular_result=PyTuple_New(data->dimensions),*normal_result=PyTuple_New(suspension ? data->dimensions : 0);
    if (!angular_result || !normal_result) { Py_XDECREF(angular_result); Py_XDECREF(normal_result); return NULL; }
    for (int a=0; a<data->dimensions; ++a) {
        PyObject *value=PyFloat_FromDouble(angular[a]);
        if (!value) { Py_DECREF(angular_result); Py_DECREF(normal_result); return NULL; }
        PyTuple_SET_ITEM(angular_result,a,value);
        if (suspension) {
            value=PyFloat_FromDouble(normal[a]);
            if (!value) { Py_DECREF(angular_result); Py_DECREF(normal_result); return NULL; }
            PyTuple_SET_ITEM(normal_result,a,value);
        }
    }
    return Py_BuildValue("(NN(ddd))",angular_result,normal_result,end_velocity[0],end_velocity[1],end_velocity[2]);
}
