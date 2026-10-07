static PyObject *load_terms_call(PyObject *self,PyObject *args,PyObject *kwargs) {
    PyObject *force_object,*response_object,*tangent_object,*axle_object,*velocity_object;
    PyObject *normal_force_object,*normal_response_object,*gradient_object,*exclude_object;
    double dt,mass;
    int dimensions;
    static char *names[]={"forces","responses","tangents","axles","velocity","dt","mass",
                         "normal_forces","normal_responses","normal_gradients","exclude","dimensions",NULL};
    if (!PyArg_ParseTupleAndKeywords(args,kwargs,"OOOOOddOOOOi",names,&force_object,&response_object,&tangent_object,
        &axle_object,&velocity_object,&dt,&mass,&normal_force_object,&normal_response_object,&gradient_object,
        &exclude_object,&dimensions)) return NULL;
    if (dimensions != 8 && dimensions != 9) {
        PyErr_SetString(PyExc_ValueError,"机械状态须为八或九维"); return NULL;
    }
    if (mass == 0.) { PyErr_SetString(PyExc_ZeroDivisionError,"机械车身质量为零"); return NULL; }
    double force[12],response[108],tangents[12],axles[12],velocity[3],end_velocity[3],terms[4],angular[9],normal[9];
    if (!matrix_values(force_object,force,4,3) || !matrix_values(tangent_object,tangents,4,3)
        || !matrix_values(axle_object,axles,4,3) || !vector(velocity_object,velocity,3)) return NULL;
    PyObject *wheels=PySequence_Fast(response_object,"轮端响应须为四轮序列");
    if (!wheels) return NULL;
    if (PySequence_Fast_GET_SIZE(wheels) != 4) {
        Py_DECREF(wheels); PyErr_SetString(PyExc_ValueError,"轮端响应须为四轮序列"); return NULL;
    }
    for (int i=0; i<4; ++i) {
        if (!matrix_values(PySequence_Fast_GET_ITEM(wheels,i),response+i*3*dimensions,3,dimensions)) {
            Py_DECREF(wheels); return NULL;
        }
    }
    Py_DECREF(wheels);
    long exclude=exclude_object == Py_None ? -1 : PyLong_AsLong(exclude_object);
    if (PyErr_Occurred()) return NULL;
    for (int a=0; a<dimensions; ++a) {
        int count=0;
        for (int i=0; i<4; ++i) {
            if (i == exclude) continue;
            terms[count++]=force[i*3]*response[(i*3)*dimensions+a]
                +force[i*3+1]*response[(i*3+1)*dimensions+a]-force[i*3+2]*response[(i*3+2)*dimensions+a];
        }
        angular[a]=dt*compensated(terms,count);
    }
    for (int a=0; a<3; ++a) {
        int count=0;
        for (int i=0; i<4; ++i) {
            if (i != exclude) terms[count++]=force[i*3]*tangents[i*3+a]+force[i*3+1]*axles[i*3+a];
        }
        end_velocity[a]=velocity[a]+dt/mass*compensated(terms,count);
    }
    int suspension=normal_force_object != Py_None;
    if (suspension) {
        double normal_forces[4],normal_responses[36],gradients[24];
        if (!vector(normal_force_object,normal_forces,4) || !matrix_values(normal_response_object,normal_responses,4,dimensions)
            || !matrix_values(gradient_object,gradients,4,6)) return NULL;
        for (int a=0; a<dimensions; ++a) {
            for (int i=0; i<4; ++i) terms[i]=normal_forces[i]*normal_responses[i*dimensions+a];
            normal[a]=dt*compensated(terms,4);
        }
        for (int a=0; a<3; ++a) {
            for (int i=0; i<4; ++i) terms[i]=normal_forces[i]*gradients[i*6+a];
            end_velocity[a]=end_velocity[a]+dt/mass*compensated(terms,4);
        }
    }
    PyObject *angular_result=PyTuple_New(dimensions),*normal_result=PyTuple_New(suspension ? dimensions : 0);
    if (!angular_result || !normal_result) { Py_XDECREF(angular_result); Py_XDECREF(normal_result); return NULL; }
    for (int a=0; a<dimensions; ++a) {
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
