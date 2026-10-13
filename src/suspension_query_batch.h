/* 同一实际候选表一次解包，逐轮遍历全部表面；只装配首命中的原记录。 */
static PyObject *surface_initial_hits(PyObject *self,PyObject *args) {
    PyObject *surfaces,*cache,*world_rays,*relative_rays,*axes,*origin_object,*surface_type,*contact_type,*coordinates;
    double radius,width,shoulder,crown;int relative;
    if(!PyArg_ParseTuple(args,"OOOOOOddddOOOp",&surfaces,&cache,&world_rays,&relative_rays,&axes,&origin_object,
        &radius,&width,&shoulder,&crown,&surface_type,&contact_type,&coordinates,&relative))return NULL;
    Py_ssize_t count=PyTuple_Size(relative_rays);if(count<0)return NULL;
    if(PyTuple_Size(world_rays)!=count||PyTuple_Size(axes)!=count){PyErr_SetString(PyExc_ValueError,"悬架射线与轮轴数量不一致");return NULL;}
    PyObject *capsule=cache==Py_None?NULL:PyDict_GetItemString(cache,"numeric_surfaces");
    SurfacePacket *packet=capsule?PyCapsule_GetPointer(capsule,surface_packet_name):NULL;
    if(capsule&&!packet)return NULL;
    if(!packet||packet->surfaces!=surfaces){capsule=surface_packet_create(surfaces);if(!capsule)return NULL;
        packet=PyCapsule_GetPointer(capsule,surface_packet_name);
        if(cache!=Py_None&&PyDict_SetItemString(cache,"numeric_surfaces",capsule)<0){Py_DECREF(capsule);return NULL;}
    }else Py_INCREF(capsule);
    PyObject *results=PyTuple_New(count),*found=NULL,*surface=NULL,*offset_object=NULL,*point_object=NULL,*contact=NULL;
    double origin[3];if(!results||!vector(origin_object,origin))goto failed;
    for(Py_ssize_t i=0;i<count;++i){double start[3],end[3],axis[3];PyObject *ray=PyTuple_GET_ITEM(relative_rays,i);
        if(!vector(PyTuple_GET_ITEM(ray,0),start)||!vector(PyTuple_GET_ITEM(ray,1),end)||!vector(PyTuple_GET_ITEM(axes,i),axis))goto failed;
        Py_ssize_t selected;
        found=surface_packet_entry(packet,start,end,axis,origin,radius,width,shoulder,crown,coordinates,&selected);
        if(!found)goto failed;
        if(found==Py_None){PyTuple_SET_ITEM(results,i,Py_NewRef(Py_None));Py_CLEAR(found);continue;}
        SurfacePart *part=&packet->parts[selected];PyObject *source=PyList_GET_ITEM(surfaces,selected);
        double offset[3],point[3],world_start[3],world_end[3],squared[3];
        for(int a=0;a<3;++a){double terms[3];for(int b=0;b<3;++b)terms[b]=part->axes[a][b]*origin[b];
            offset[a]=part->translation[a]+sum_three(terms);}
        ray=PyTuple_GET_ITEM(world_rays,i);
        if(!vector(PyTuple_GET_ITEM(ray,0),world_start)||!vector(PyTuple_GET_ITEM(ray,1),world_end)
            ||!vector(PyTuple_GET_ITEM(found,2),point))goto failed;
        for(int a=0;a<3;++a){squared[a]=pow(world_end[a]-world_start[a],2.);if(!relative)point[a]+=origin[a];}
        offset_object=Py_BuildValue("(ddd)",offset[0],offset[1],offset[2]);
        point_object=Py_BuildValue("(ddd)",point[0],point[1],point[2]);
        if(!offset_object||!point_object)goto failed;
        surface=PyObject_CallFunction(surface_type,"OOOOddddOOdO",PyTuple_GET_ITEM(source,3),PyTuple_GET_ITEM(source,4),
            PyTuple_GET_ITEM(source,2),offset_object,radius,sqrt(sum_three(squared))-radius,width,shoulder,
            PyTuple_GET_ITEM(axes,i),PyTuple_GET_ITEM(source,5),crown,PyTuple_GET_ITEM(source,6));
        if(!surface)goto failed;
        contact=PyObject_CallFunctionObjArgs(contact_type,PyTuple_GET_ITEM(source,0),PyTuple_GET_ITEM(found,0),
            point_object,PyTuple_GET_ITEM(found,1),surface,PyTuple_GET_ITEM(found,3),NULL);
        if(!contact)goto failed;
        PyTuple_SET_ITEM(results,i,contact);contact=NULL;
        Py_CLEAR(found);Py_CLEAR(surface);Py_CLEAR(offset_object);Py_CLEAR(point_object);
    }
    Py_DECREF(capsule);return results;
failed:
    Py_DECREF(capsule);Py_XDECREF(results);Py_XDECREF(found);Py_XDECREF(surface);
    Py_XDECREF(offset_object);Py_XDECREF(point_object);Py_XDECREF(contact);return NULL;
}
