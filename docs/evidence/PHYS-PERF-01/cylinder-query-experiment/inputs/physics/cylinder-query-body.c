/* 真实射线的相对/世界坐标与原覆盖盒；不查询世界、不扩大包络。 */
static PyObject *cylinder_query_frame(PyObject *self,PyObject *args) {
    PyObject *rays,*origin_object;
    double radius,width;
    int relative;
    if (!PyArg_ParseTuple(args,"OOddp",&rays,&origin_object,&radius,&width,&relative)) return NULL;
    double origin[3],low[3],high[3],padding=radius+width/2+1e-5;
    if (!vector(origin_object,origin)) return NULL;
    PyObject *sequence=PySequence_Fast(rays,"支持射线须为序列");
    if (!sequence) return NULL;
    Py_ssize_t count=PySequence_Fast_GET_SIZE(sequence);
    if (!count) {Py_DECREF(sequence); PyErr_SetString(PyExc_ValueError,"min() iterable argument is empty"); return NULL;}
    PyObject *converted=PyTuple_New(count);
    if (!converted) {Py_DECREF(sequence); return NULL;}
    for (Py_ssize_t i=0; i<count; ++i) {
        PyObject *ray=PySequence_Fast(PySequence_Fast_GET_ITEM(sequence,i),"支持射线须含起止点");
        if (!ray) {Py_DECREF(converted); Py_DECREF(sequence); return NULL;}
        if (PySequence_Fast_GET_SIZE(ray)!=2) {
            Py_DECREF(ray); Py_DECREF(converted); Py_DECREF(sequence);
            PyErr_SetString(PyExc_ValueError,"支持射线须含两个端点"); return NULL;
        }
        PyObject *converted_ray=PyTuple_New(2);
        if (!converted_ray) {Py_DECREF(ray); Py_DECREF(converted); Py_DECREF(sequence); return NULL;}
        PyTuple_SET_ITEM(converted,i,converted_ray);
        for (int j=0; j<2; ++j) {
            double point[3],other[3],world[3];
            if (!vector(PySequence_Fast_GET_ITEM(ray,j),point)) {Py_DECREF(ray); Py_DECREF(converted); Py_DECREF(sequence); return NULL;}
            for (int a=0; a<3; ++a) {
                other[a]=relative ? point[a]+origin[a] : point[a]-origin[a];
                world[a]=relative ? other[a] : point[a];
                if (i==0 && j==0) low[a]=high[a]=world[a];
                else {
                    if (world[a]<low[a]) low[a]=world[a];
                    if (world[a]>high[a]) high[a]=world[a];
                }
            }
            PyObject *tuple=Py_BuildValue("(ddd)",other[0],other[1],other[2]);
            if (!tuple) {Py_DECREF(ray); Py_DECREF(converted); Py_DECREF(sequence); return NULL;}
            PyTuple_SET_ITEM(converted_ray,j,tuple);
        }
        Py_DECREF(ray);
    }
    Py_DECREF(sequence);
    for (int a=0; a<3; ++a) {low[a]-=padding; high[a]+=padding;}
    PyObject *box_low=Py_BuildValue("(ddd)",low[0],low[1],low[2]);
    PyObject *box_high=Py_BuildValue("(ddd)",high[0],high[1],high[2]);
    if (!box_low || !box_high) {Py_XDECREF(box_low); Py_XDECREF(box_high); Py_DECREF(converted); return NULL;}
    PyObject *result=PyTuple_Pack(4,relative ? rays : converted,relative ? converted : rays,box_low,box_high);
    Py_DECREF(box_high); Py_DECREF(box_low); Py_DECREF(converted); return result;
}
