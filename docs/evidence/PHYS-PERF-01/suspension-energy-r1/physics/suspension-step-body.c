/* 完整悬架步直接组合原接触解和能量账，Python只发布原SuspensionStep。 */
static PyObject *suspension_step(PyObject *self,PyObject *args) {
    PyObject *compression,*speed,*mobility,*touching,*rates_object,*cd,*ed,*bars_object,*stops,*geometry;
    double travel,dt,rates[4],bars[2],matrix[16]={0.};
    if (!PyArg_ParseTuple(args,"OOOOOOOOOddO",&compression,&speed,&mobility,&touching,&rates_object,
        &cd,&ed,&bars_object,&stops,&travel,&dt,&geometry)) return NULL;
    if (!vector(rates_object,rates,4) || !vector(bars_object,bars,2)) return NULL;
    for (int i=0; i<4; ++i) matrix[i*4+i]=rates[i];
    for (int axle=0; axle<2; ++axle) {
        int left=2*axle,right=left+1;
        matrix[left*4+left]+=bars[axle]; matrix[right*4+right]+=bars[axle];
        matrix[left*4+right]-=bars[axle]; matrix[right*4+left]-=bars[axle];
    }
    PyObject *stiffness=Py_BuildValue("((dddd)(dddd)(dddd)(dddd))",matrix[0],matrix[1],matrix[2],matrix[3],
        matrix[4],matrix[5],matrix[6],matrix[7],matrix[8],matrix[9],matrix[10],matrix[11],matrix[12],matrix[13],matrix[14],matrix[15]);
    if (!stiffness) return NULL;
    PyObject *contact_args=Py_BuildValue("(OOOOOOOOddO)",compression,speed,mobility,touching,
        stiffness,cd,ed,stops,travel,dt,geometry);
    Py_DECREF(stiffness);
    if (!contact_args) return NULL;
    PyObject *contact=suspension_contact_state(self,contact_args);
    Py_DECREF(contact_args);
    if (!contact) return NULL;
    PyObject *energy_args=Py_BuildValue("(OOOdOOOOOOdO)",compression,speed,mobility,dt,geometry,
        PyTuple_GET_ITEM(contact,0),PyTuple_GET_ITEM(contact,1),rates_object,bars_object,stops,travel,PyTuple_GET_ITEM(contact,3));
    if (!energy_args) { Py_DECREF(contact); return NULL; }
    PyObject *energy=suspension_energy_account(self,energy_args);
    Py_DECREF(energy_args);
    if (!energy) { Py_DECREF(contact); return NULL; }
    PyObject *result=PyTuple_New(13);
    if (!result) { Py_DECREF(energy); Py_DECREF(contact); return NULL; }
    PyTuple_SET_ITEM(result,0,Py_NewRef(PyTuple_GET_ITEM(contact,0)));
    PyTuple_SET_ITEM(result,1,Py_NewRef(PyTuple_GET_ITEM(energy,0)));
    PyTuple_SET_ITEM(result,2,Py_NewRef(PyTuple_GET_ITEM(contact,1)));
    PyTuple_SET_ITEM(result,3,Py_NewRef(PyTuple_GET_ITEM(contact,2)));
    for (int i=1; i<10; ++i) PyTuple_SET_ITEM(result,3+i,Py_NewRef(PyTuple_GET_ITEM(energy,i)));
    Py_DECREF(energy); Py_DECREF(contact); return result;
}
