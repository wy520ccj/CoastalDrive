/* 批量读取唯一世界的静态资格和实际签名；只复用逐值未改变的原几何。 */
static PyObject *support_read_tag(PyObject *body,PyObject *has,PyObject *get,PyObject *tag) {
    PyObject *present=PyObject_CallMethodOneArg(body,has,tag);if(!present)return NULL;
    int yes=PyObject_IsTrue(present);Py_DECREF(present);if(yes<0)return NULL;
    return yes?PyObject_CallMethodOneArg(body,get,tag):Py_NewRef(Py_None);
}

static PyObject *static_support_read(PyObject *self,PyObject *args) {
    PyObject *world,*chassis,*mask,*cache,*node_path,*types,*unit_scale,*bounds_function;
    if(!PyArg_ParseTuple(args,"OOOOOOOO",&world,&chassis,&mask,&cache,&node_path,&types,&unit_scale,&bounds_function))return NULL;
    if((cache!=Py_None&&!PyDict_Check(cache))||!PyTuple_Check(types)||PyTuple_GET_SIZE(types)!=4){
        PyErr_SetString(PyExc_TypeError,"静态缓存须为字典，形状类型须为四元组");return NULL;}
    enum {BODIES,STATIC,MASK,ZERO,NAME,TRANSFORM,POS,SHAPES,HAS_TAG,GET_TAG,NET,SHAPE_POSE,MARGIN,SCALE,MAT,
          MESH_TAG,BOUNDS_TAG,VERTICES_TAG,HULLS_TAG,NAME_COUNT};
    const char *texts[]={"getRigidBodies","isStatic","getIntoCollideMask","isZero","getName","getTransform",
        "getPos","getShapes","hasPythonTag","getPythonTag","getNetTransform","getShapeTransform","getMargin",
        "getScale","getMat","suspension_mesh","suspension_shape_bounds","suspension_hull_vertices","suspension_hull_shapes"};
    PyObject *names[NAME_COUNT]={0},*bodies=NULL,*ordered=NULL,*groups=NULL,*hulls=NULL,*updates=NULL,*active=NULL;
    PyObject *v[15]={0},*shape_mats=NULL,*mutable_bounds=NULL,*signature=NULL;
    for(int i=0;i<NAME_COUNT;++i){names[i]=PyUnicode_InternFromString(texts[i]);if(!names[i])goto failed;}
    bodies=PyObject_CallMethodNoArgs(world,names[BODIES]);if(!bodies)goto failed;
    v[0]=PySequence_Fast(bodies,"世界刚体须为序列");if(!v[0])goto failed;
    ordered=PyList_New(0);if(!ordered)goto failed;
    for(Py_ssize_t i=0;i<PySequence_Fast_GET_SIZE(v[0]);++i){PyObject *body=PySequence_Fast_GET_ITEM(v[0],i);
        int different=PyObject_RichCompareBool(body,chassis,Py_NE);if(different<0)goto failed;if(!different)continue;
        v[1]=PyObject_CallMethodNoArgs(body,names[STATIC]);if(!v[1])goto failed;
        int is_static=PyObject_IsTrue(v[1]);Py_CLEAR(v[1]);if(is_static<0)goto failed;if(!is_static)continue;
        v[1]=PyObject_CallMethodNoArgs(body,names[MASK]);if(!v[1])goto failed;
        v[2]=PyNumber_And(v[1],mask);Py_CLEAR(v[1]);if(!v[2])goto failed;
        v[1]=PyObject_CallMethodNoArgs(v[2],names[ZERO]);Py_CLEAR(v[2]);if(!v[1])goto failed;
        int zero=PyObject_IsTrue(v[1]);Py_CLEAR(v[1]);if(zero<0)goto failed;if(zero)continue;
        v[1]=PyObject_CallMethodNoArgs(body,names[NAME]);v[2]=PyObject_CallMethodNoArgs(body,names[TRANSFORM]);
        if(!v[1]||!v[2])goto failed;v[3]=PyObject_CallMethodNoArgs(v[2],names[POS]);Py_CLEAR(v[2]);if(!v[3])goto failed;
        v[2]=PySequence_Tuple(v[3]);Py_CLEAR(v[3]);if(!v[2])goto failed;
        /* 原始索引只在名称/位置相同的情况下保持原稳定排序，不比较刚体对象。 */
        v[3]=Py_BuildValue("OOnO",v[1],v[2],i,body);Py_CLEAR(v[1]);Py_CLEAR(v[2]);if(!v[3])goto failed;
        if(PyList_Append(ordered,v[3])<0)goto failed;Py_CLEAR(v[3]);
    }
    Py_CLEAR(v[0]);if(PyList_Sort(ordered)<0)goto failed;
    groups=PyList_New(PyList_GET_SIZE(ordered));hulls=PyDict_New();updates=PyList_New(0);active=PySet_New(NULL);
    if(!groups||!hulls||!updates||!active)goto failed;
    for(Py_ssize_t i=0;i<PyList_GET_SIZE(ordered);++i){PyObject *body=PyTuple_GET_ITEM(PyList_GET_ITEM(ordered,i),3);
        if(PySet_Add(active,body)<0)goto failed;
        v[0]=PyObject_CallMethodNoArgs(body,names[SHAPES]);if(!v[0])goto failed;
        v[1]=PySequence_Tuple(v[0]);Py_CLEAR(v[0]);if(!v[1])goto failed;
        Py_ssize_t count=PyTuple_GET_SIZE(v[1]);
        v[2]=support_read_tag(body,names[HAS_TAG],names[GET_TAG],names[MESH_TAG]);
        v[3]=support_read_tag(body,names[HAS_TAG],names[GET_TAG],names[BOUNDS_TAG]);if(!v[2]||!v[3])goto failed;
        int supported=count!=0;
        for(Py_ssize_t j=0;j<count&&supported;++j){PyObject *shape=PyTuple_GET_ITEM(v[1],j);
            int box=PyObject_IsInstance(shape,PyTuple_GET_ITEM(types,0));if(box<0)goto failed;
            int plane=box?0:PyObject_IsInstance(shape,PyTuple_GET_ITEM(types,1));if(plane<0)goto failed;
            int mesh=(box||plane)?0:PyObject_IsInstance(shape,PyTuple_GET_ITEM(types,2));if(mesh<0)goto failed;
            supported=box||plane||(mesh&&v[2]!=Py_None&&count==1);}
        v[4]=PyObject_CallOneArg(node_path,body);if(!v[4])goto failed;
        v[5]=PyObject_CallMethodNoArgs(v[4],names[NET]);Py_CLEAR(v[4]);if(!v[5])goto failed;
        v[6]=PyTuple_New(count);v[7]=PyTuple_New(count);shape_mats=PyTuple_New(count);mutable_bounds=PyTuple_New(count);
        if(!v[6]||!v[7]||!shape_mats||!mutable_bounds)goto failed;
        for(Py_ssize_t j=0;j<count;++j){PyObject *shape=PyTuple_GET_ITEM(v[1],j);
            v[8]=PyLong_FromSsize_t(j);if(!v[8])goto failed;
            v[9]=PyObject_CallMethodOneArg(body,names[SHAPE_POSE],v[8]);Py_CLEAR(v[8]);if(!v[9])goto failed;
            v[8]=PyObject_CallMethodNoArgs(v[9],names[MAT]);if(!v[8])goto failed;
            PyTuple_SET_ITEM(shape_mats,j,v[8]);v[8]=NULL;PyTuple_SET_ITEM(v[6],j,v[9]);v[9]=NULL;
            v[8]=PyObject_CallMethodNoArgs(shape,names[MARGIN]);if(!v[8])goto failed;
            PyTuple_SET_ITEM(v[7],j,v[8]);v[8]=NULL;
            int convex=v[3]==Py_None?PyObject_IsInstance(shape,PyTuple_GET_ITEM(types,3)):0;if(convex<0)goto failed;
            v[8]=convex?PyObject_CallFunctionObjArgs(bounds_function,shape,Py_None,NULL):Py_NewRef(Py_None);
            if(!v[8])goto failed;PyTuple_SET_ITEM(mutable_bounds,j,v[8]);v[8]=NULL;
        }
        v[8]=PyObject_CallMethodOneArg(body,names[HAS_TAG],names[VERTICES_TAG]);if(!v[8])goto failed;
        int has_vertices=PyObject_IsTrue(v[8]);Py_CLEAR(v[8]);if(has_vertices<0)goto failed;
        v[10]=Py_NewRef(Py_None);
        if(has_vertices){v[8]=PyObject_CallMethodOneArg(body,names[GET_TAG],names[HULLS_TAG]);if(!v[8])goto failed;
            int same=PyObject_RichCompareBool(v[1],v[8],Py_EQ);Py_CLEAR(v[8]);if(same<0)goto failed;
            if(same){v[8]=PyObject_CallMethodNoArgs(v[5],names[SCALE]);if(!v[8])goto failed;
                int unit=PyObject_RichCompareBool(v[8],unit_scale,Py_EQ);Py_CLEAR(v[8]);if(unit<0)goto failed;
                if(unit){Py_CLEAR(v[10]);v[10]=PyObject_CallMethodOneArg(body,names[GET_TAG],names[VERTICES_TAG]);if(!v[10])goto failed;}}}
        v[11]=PyObject_CallMethodNoArgs(v[5],names[MAT]);if(!v[11])goto failed;
        v[12]=PyLong_FromVoidPtr(v[2]);v[13]=PyLong_FromVoidPtr(v[3]);v[14]=PyLong_FromVoidPtr(v[10]);
        if(!v[12]||!v[13]||!v[14])goto failed;
        signature=PyTuple_Pack(8,v[11],v[1],shape_mats,v[7],v[12],v[13],mutable_bounds,v[14]);if(!signature)goto failed;
        PyObject *previous=cache==Py_None?NULL:PyDict_GetItemWithError(cache,body);if(!previous&&PyErr_Occurred())goto failed;
        if(previous&&(!PyTuple_Check(previous)||PyTuple_GET_SIZE(previous)!=3)){
            PyErr_SetString(PyExc_ValueError,"静态缓存记录须含签名/几何/凸体");goto failed;}
        int unchanged=previous?PyObject_RichCompareBool(PyTuple_GET_ITEM(previous,0),signature,Py_EQ):0;if(unchanged<0)goto failed;
        if(unchanged){PyList_SET_ITEM(groups,i,Py_NewRef(PyTuple_GET_ITEM(previous,1)));
            if(PyTuple_GET_ITEM(previous,2)!=Py_None&&PyDict_SetItem(hulls,body,PyTuple_GET_ITEM(previous,2))<0)goto failed;}
        else {PyList_SET_ITEM(groups,i,Py_NewRef(Py_None));
            PyObject *record=Py_BuildValue("nOOOOOOOOO",i,body,supported?Py_True:Py_False,v[1],v[2],v[3],v[5],v[6],v[7],v[10]);
            if(!record)goto failed;
            PyObject *update=PyTuple_Pack(2,record,signature);Py_DECREF(record);if(!update)goto failed;
            int appended=PyList_Append(updates,update);Py_DECREF(update);if(appended<0)goto failed;}
        for(int j=0;j<15;++j)Py_CLEAR(v[j]);Py_CLEAR(shape_mats);Py_CLEAR(mutable_bounds);Py_CLEAR(signature);
    }
    if(cache!=Py_None){v[0]=PyDict_Keys(cache);if(!v[0])goto failed;
        for(Py_ssize_t i=0;i<PyList_GET_SIZE(v[0]);++i){PyObject *body=PyList_GET_ITEM(v[0],i);
            int present=PySet_Contains(active,body);if(present<0)goto failed;
            if(!present&&PyDict_DelItem(cache,body)<0)goto failed;}Py_CLEAR(v[0]);}
    PyObject *result=PyTuple_Pack(3,groups,hulls,updates);
    for(int i=0;i<NAME_COUNT;++i)Py_XDECREF(names[i]);Py_DECREF(bodies);Py_DECREF(ordered);Py_DECREF(groups);
    Py_DECREF(hulls);Py_DECREF(updates);Py_DECREF(active);return result;
failed:
    for(int i=0;i<15;++i)Py_XDECREF(v[i]);for(int i=0;i<NAME_COUNT;++i)Py_XDECREF(names[i]);
    Py_XDECREF(bodies);Py_XDECREF(ordered);Py_XDECREF(groups);Py_XDECREF(hulls);Py_XDECREF(updates);Py_XDECREF(active);
    Py_XDECREF(shape_mats);Py_XDECREF(mutable_bounds);Py_XDECREF(signature);return NULL;
}
