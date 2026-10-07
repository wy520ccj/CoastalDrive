
/* 原索引的有序筛选、有限面与首接点在一次查询内完成，边角仍交给原求解函数。 */
static int triangle_query_possible(PyObject *center_object,PyObject *half_object,
                                   double start[3],double end[3],double padding[3]) {
    double center[3],base_half[3],half[3],local_start[3],local_end[3],entry,exit_time,sign;
    int axis;
    if (!vector(center_object,center) || !vector(half_object,base_half)) return -1;
    for (int i=0; i<3; ++i) {
        half[i]=base_half[i]+padding[i]; local_start[i]=start[i]-center[i]; local_end[i]=end[i]-center[i];
    }
    return box_interval_values(local_start,local_end,half,&entry,&exit_time,&axis,&sign)
        && entry<=1. && exit_time>=0.;
}
static int triangle_query_collect(PyObject *node,double start[3],double end[3],double padding[3],PyObject *result) {
    PyObject *center=PyObject_GetAttrString(node,"center"),*half=PyObject_GetAttrString(node,"half");
    PyObject *children=NULL,*triangles=NULL,*bounds=NULL;
    int status=0;
    if (!center || !half) goto done;
    int possible=triangle_query_possible(center,half,start,end,padding);
    if (possible<0) goto done;
    if (!possible) { status=1; goto done; }
    children=PyObject_GetAttrString(node,"children");
    triangles=PyObject_GetAttrString(node,"triangles");
    bounds=PyObject_GetAttrString(node,"triangle_bounds");
    if (!children || !triangles || !bounds) goto done;
    if (!PyTuple_Check(children) || !PyTuple_Check(triangles) || !PyTuple_Check(bounds)
        || PyTuple_GET_SIZE(triangles)!=PyTuple_GET_SIZE(bounds)) {
        PyErr_SetString(PyExc_ValueError,"三角面索引结构不一致"); goto done;
    }
    for (Py_ssize_t i=0; i<PyTuple_GET_SIZE(children); ++i)
        if (!triangle_query_collect(PyTuple_GET_ITEM(children,i),start,end,padding,result)) goto done;
    for (Py_ssize_t i=0; i<PyTuple_GET_SIZE(triangles); ++i) {
        PyObject *bound=PyTuple_GET_ITEM(bounds,i);
        if (!PyTuple_Check(bound) || PyTuple_GET_SIZE(bound)!=2) {
            PyErr_SetString(PyExc_ValueError,"原三角面边界结构不一致"); goto done;
        }
        possible=triangle_query_possible(PyTuple_GET_ITEM(bound,0),PyTuple_GET_ITEM(bound,1),start,end,padding);
        if (possible<0) goto done;
        if (possible && PyList_Append(result,PyTuple_GET_ITEM(triangles,i))<0) goto done;
    }
    status=1;
done:
    Py_XDECREF(center); Py_XDECREF(half); Py_XDECREF(children); Py_XDECREF(triangles); Py_XDECREF(bounds);
    return status;
}
static int triangle_query_best(PyObject *hit,PyObject **best,double *ceiling) {
    double fraction=PyFloat_AsDouble(PyTuple_GetItem(hit,0));
    if (PyErr_Occurred()) return 0;
    if (!*best || fraction<*ceiling) {
        Py_XSETREF(*best,Py_NewRef(hit)); *ceiling=fraction;
    }
    return 1;
}
static PyObject *triangle_support_entry(PyObject *self,PyObject *args,PyObject *kwargs) {
    PyObject *node,*start_object,*end_object,*margin_object,*axis_object,*radius_object,*width_object,*shoulder_object,*crown_object,*edge_entry;
    static char *names[]={"node","start","end","margin","axis","radius","width","shoulder","crown","edge_entry",NULL};
    if (!PyArg_ParseTupleAndKeywords(args,kwargs,"OOOOOOOOOO",names,&node,&start_object,&end_object,&margin_object,
        &axis_object,&radius_object,&width_object,&shoulder_object,&crown_object,&edge_entry)) return NULL;
    double start[3],end[3],axis[3],padding[3],margin=PyFloat_AsDouble(margin_object),radius=PyFloat_AsDouble(radius_object);
    double width=PyFloat_AsDouble(width_object),shoulder=PyFloat_AsDouble(shoulder_object),crown=PyFloat_AsDouble(crown_object);
    if (PyErr_Occurred() || !vector(start_object,start) || !vector(end_object,end) || !vector(axis_object,axis)) return NULL;
    for (int i=0; i<3; ++i) {
        double direction[3]={0.},support[3]; direction[i]=1.;
        if (!support_values(direction,axis,radius,width/2,shoulder,crown,support)) return NULL;
        padding[i]=support[i]+margin;
    }
    PyObject *candidates=PyList_New(0),*curved=PyList_New(0),*best=NULL,*keywords=NULL;
    double ceiling=1.;
    if (!candidates || !curved || !triangle_query_collect(node,start,end,padding,candidates)) goto error;
    for (Py_ssize_t k=0; k<PyList_GET_SIZE(candidates); ++k) {
        PyObject *triangle=PyList_GET_ITEM(candidates,k);
        double vertices[3][3];
        if (!PyTuple_Check(triangle) || PyTuple_GET_SIZE(triangle)!=3) {
            PyErr_SetString(PyExc_ValueError,"三角面须为三个顶点"); goto error;
        }
        for (int i=0; i<3; ++i) if (!vector(PyTuple_GET_ITEM(triangle,i),vertices[i])) goto error;
        PyObject *result=triangle_face_values(start,end,vertices,margin,axis,radius,width,shoulder,crown,1,1.);
        if (!result) goto error;
        PyObject *hit=PyTuple_GET_ITEM(result,1);
        int kept=hit!=Py_None ? triangle_query_best(hit,&best,&ceiling) : PyList_Append(curved,triangle)>=0;
        Py_DECREF(result);
        if (!kept) goto error;
    }
    keywords=PyDict_New();
    if (!keywords) goto error;
    for (Py_ssize_t k=0; k<PyList_GET_SIZE(curved); ++k) {
        PyObject *arguments=PyTuple_Pack(9,start_object,end_object,PyList_GET_ITEM(curved,k),margin_object,axis_object,
                                         radius_object,width_object,shoulder_object,crown_object);
        if (!arguments) goto error;
        PyObject *limit=PyFloat_FromDouble(ceiling);
        if (!limit) { Py_DECREF(arguments); goto error; }
        int updated=PyDict_SetItemString(keywords,"ceiling",limit); Py_DECREF(limit);
        if (updated<0) { Py_DECREF(arguments); goto error; }
        PyObject *hit=PyObject_Call(edge_entry,arguments,keywords); Py_DECREF(arguments);
        if (!hit) goto error;
        int kept=hit==Py_None || triangle_query_best(hit,&best,&ceiling);
        Py_DECREF(hit);
        if (!kept) goto error;
    }
    Py_DECREF(candidates); Py_DECREF(curved); Py_DECREF(keywords);
    return best ? best : Py_NewRef(Py_None);
error:
    Py_XDECREF(candidates); Py_XDECREF(curved); Py_XDECREF(best); Py_XDECREF(keywords);
    return NULL;
}
