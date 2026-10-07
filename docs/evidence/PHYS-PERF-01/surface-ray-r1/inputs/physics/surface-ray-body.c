/* 保留支持面和接点对象，只合并同一射线的数值变换与有序结果装配。 */
static PyObject *surface_ray_hits(PyObject *self,PyObject *args) {
    PyObject *surfaces,*start_object,*end_object,*axis_object,*origin_object,*surface_class,*contact_class;
    double radius,reach,width,shoulder,crown;
    int relative;
    if (!PyArg_ParseTuple(args,"OOOOOdddddOO p",&surfaces,&start_object,&end_object,&axis_object,&origin_object,
                         &radius,&reach,&width,&shoulder,&crown,&surface_class,&contact_class,&relative)) return NULL;
    double start[3],end[3],origin[3];
    if (!vector(start_object,start) || !vector(end_object,end) || !vector(origin_object,origin)) return NULL;
    PyObject *hits=PyList_New(0);
    if (!hits) return NULL;
    for (Py_ssize_t k=0; k<PyTuple_GET_SIZE(surfaces); ++k) {
        PyObject *part=PyTuple_GET_ITEM(surfaces,k),*body=PyTuple_GET_ITEM(part,0),*inverse=PyTuple_GET_ITEM(part,1);
        PyObject *frame=PyTuple_GET_ITEM(part,2),*half=PyTuple_GET_ITEM(part,3),*margin=PyTuple_GET_ITEM(part,4);
        PyObject *plane=PyTuple_GET_ITEM(part,5),*triangles=PyTuple_GET_ITEM(part,6);
        double axes[3][3],offset[3],local_start[3],local_end[3];
        PyObject *surface=NULL,*found=NULL,*offset_object=NULL,*local_a=NULL,*local_b=NULL,*normal_object=NULL,*point_object=NULL,*hit=NULL;
        for (int a=0; a<3; ++a) {
            if (!vector(PyTuple_GET_ITEM(frame,a),axes[a])) goto failure;
            PyObject *cell=PyObject_CallMethod(inverse,"getCell","ii",3,a);
            if (!cell) goto failure;
            double translation=PyFloat_AsDouble(cell); Py_DECREF(cell);
            if (PyErr_Occurred()) goto failure;
            double terms[3];
            for (int b=0; b<3; ++b) terms[b]=axes[a][b]*origin[b];
            offset[a]=translation+sum_three(terms);
        }
        offset_object=Py_BuildValue("(ddd)",offset[0],offset[1],offset[2]);
        if (!offset_object) goto failure;
        surface=PyObject_CallFunction(surface_class,"OOOOddddOOdO",half,margin,frame,offset_object,
                                      radius,reach,width,shoulder,axis_object,plane,crown,triangles);
        if (!surface) goto failure;
        transform_values(start,axes,offset,0,local_start);
        transform_values(end,axes,offset,0,local_end);
        local_a=Py_BuildValue("(ddd)",local_start[0],local_start[1],local_start[2]);
        local_b=Py_BuildValue("(ddd)",local_end[0],local_end[1],local_end[2]);
        if (!local_a || !local_b) goto failure;
        found=PyObject_CallMethod(surface,"entry","OOO",local_a,local_b,axis_object);
        if (!found) goto failure;
        if (found!=Py_None) {
            double normal[3],point[3],world_normal[3],world_point[3],zero[3]={0.};
            if (!vector(PyTuple_GET_ITEM(found,1),normal) || !vector(PyTuple_GET_ITEM(found,2),point)) goto failure;
            for (int a=0; a<3; ++a) point[a]=point[a]-offset[a];
            transform_values(normal,axes,zero,1,world_normal);
            transform_values(point,axes,zero,1,world_point);
            if (!relative) for (int a=0; a<3; ++a) world_point[a]=world_point[a]+origin[a];
            normal_object=Py_BuildValue("(ddd)",world_normal[0],world_normal[1],world_normal[2]);
            point_object=Py_BuildValue("(ddd)",world_point[0],world_point[1],world_point[2]);
            if (!normal_object || !point_object) goto failure;
            hit=PyObject_CallFunctionObjArgs(contact_class,body,PyTuple_GET_ITEM(found,0),point_object,normal_object,
                                            surface,PyTuple_GET_ITEM(found,3),NULL);
            if (!hit || PyList_Append(hits,hit)<0) goto failure;
        }
        Py_XDECREF(hit); Py_XDECREF(point_object); Py_XDECREF(normal_object);
        Py_DECREF(found); Py_DECREF(local_b); Py_DECREF(local_a); Py_DECREF(surface); Py_DECREF(offset_object);
        continue;
failure:
        Py_XDECREF(hit); Py_XDECREF(point_object); Py_XDECREF(normal_object);
        Py_XDECREF(found); Py_XDECREF(local_b); Py_XDECREF(local_a); Py_XDECREF(surface); Py_XDECREF(offset_object);
        Py_DECREF(hits); return NULL;
    }
    return hits;
}
