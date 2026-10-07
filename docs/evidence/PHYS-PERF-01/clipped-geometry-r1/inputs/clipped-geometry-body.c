
/* 几何差量保留原逐元素减法和较短序列的元组输出。 */
static PyObject *subtract_vector(PyObject *self,PyObject *args,PyObject *kwargs) {
    PyObject *first,*second;
    static char *names[]={"a","b",NULL};
    if (!PyArg_ParseTupleAndKeywords(args,kwargs,"OO",names,&first,&second)) return NULL;
    PyObject *a=PySequence_Fast(first,"几何向量须为序列"),*b=PySequence_Fast(second,"几何向量须为序列");
    if (!a || !b) { Py_XDECREF(a); Py_XDECREF(b); return NULL; }
    Py_ssize_t n=PySequence_Fast_GET_SIZE(a)<PySequence_Fast_GET_SIZE(b) ? PySequence_Fast_GET_SIZE(a) : PySequence_Fast_GET_SIZE(b);
    PyObject *result=PyTuple_New(n);
    if (!result) { Py_DECREF(a); Py_DECREF(b); return NULL; }
    for (Py_ssize_t i=0; i<n; ++i) {
        PyObject *value=PyNumber_Subtract(PySequence_Fast_GET_ITEM(a,i),PySequence_Fast_GET_ITEM(b,i));
        if (!value) { Py_DECREF(a); Py_DECREF(b); Py_DECREF(result); return NULL; }
        PyTuple_SET_ITEM(result,i,value);
    }
    Py_DECREF(a); Py_DECREF(b); return result;
}

/* 原六个覆盖盒裁剪平面及fma交点；保留顶点次序和未改变顶点的对象。 */
static PyObject *clipped_triangle_call(PyObject *self,PyObject *args,PyObject *kwargs) {
    PyObject *triangle,*start_object,*end_object,*padding_object;
    static char *names[]={"triangle","start","end","padding",NULL};
    if (!PyArg_ParseTupleAndKeywords(args,kwargs,"OOOO",names,&triangle,&start_object,&end_object,&padding_object)) return NULL;
    double start[3],end[3],padding[3];
    if (!vector(start_object,start) || !vector(end_object,end) || !vector(padding_object,padding)) return NULL;
    PyObject *polygon=PySequence_List(triangle);
    if (!polygon) return NULL;
    for (int axis=0; axis<3; ++axis) for (int side=0; side<2; ++side) {
        double sign=side==0 ? 1. : -1.;
        double bound=side==0 ? (end[axis]<start[axis] ? end[axis] : start[axis])-padding[axis]
                            : (end[axis]>start[axis] ? end[axis] : start[axis])+padding[axis];
        PyObject *result=PyList_New(0);
        if (!result) { Py_DECREF(polygon); return NULL; }
        Py_ssize_t n=PyList_GET_SIZE(polygon);
        for (Py_ssize_t i=0; i<n; ++i) {
            PyObject *a_object=PyList_GET_ITEM(polygon,i),*b_object=PyList_GET_ITEM(polygon,(i+1)%n);
            double a[3],b[3];
            if (!vector(a_object,a) || !vector(b_object,b)) { Py_DECREF(polygon); Py_DECREF(result); return NULL; }
            double da=sign*(a[axis]-bound),db=sign*(b[axis]-bound);
            if (da>=0. && PyList_Append(result,a_object)<0) { Py_DECREF(polygon); Py_DECREF(result); return NULL; }
            if ((da>=0.)!=(db>=0.)) {
                double fraction=da/(da-db),point[3];
                for (int j=0; j<3; ++j) point[j]=j==axis ? bound : fma(fraction,b[j]-a[j],a[j]);
                PyObject *vertex=Py_BuildValue("(ddd)",point[0],point[1],point[2]);
                if (!vertex) { Py_DECREF(polygon); Py_DECREF(result); return NULL; }
                int appended=PyList_Append(result,vertex); Py_DECREF(vertex);
                if (appended<0) { Py_DECREF(polygon); Py_DECREF(result); return NULL; }
            }
        }
        Py_SETREF(polygon,result);
    }
    return polygon;
}
