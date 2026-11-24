/* 批量读取唯一世界的静态资格和实际签名；只复用逐值未改变的原几何。 */
static PyObject *support_read_tag(PyObject *body,PyObject *has,PyObject *get,PyObject *tag) {
    PyObject *present=PyObject_CallMethodOneArg(body,has,tag);if(!present)return NULL;
    int yes=PyObject_IsTrue(present);Py_DECREF(present);if(yes<0)return NULL;
    return yes?PyObject_CallMethodOneArg(body,get,tag):Py_NewRef(Py_None);
}

enum {
    SSR_BODIES,SSR_STATIC,SSR_MASK,SSR_WORD,SSR_NAME,SSR_TRANSFORM,SSR_POS,SSR_SHAPES,SSR_NUM_SHAPES,
    SSR_GET_SHAPE,SSR_NUM_PARENTS,SSR_HAS_TAG,SSR_GET_TAG,SSR_NET,SSR_SHAPE_POSE,SSR_MARGIN,SSR_SCALE,
    SSR_MAT,SSR_MESH_TAG,SSR_BOUNDS_TAG,SSR_VERTICES_TAG,SSR_HULLS_TAG,SSR_NAME_COUNT
};
static PyObject *ssr_names[SSR_NAME_COUNT]={0};
static PyObject *ssr_zero_index=NULL;

static int ssr_init_names(void) {
    if(ssr_names[0]&&ssr_zero_index)return 1;
    const char *texts[SSR_NAME_COUNT]={
        "getRigidBodies","isStatic","getIntoCollideMask","getWord","getName","getTransform","getPos",
        "getShapes","getNumShapes","getShape","getNumParents","hasPythonTag","getPythonTag",
        "getNetTransform","getShapeTransform","getMargin","getScale","getMat","suspension_mesh",
        "suspension_shape_bounds","suspension_hull_vertices","suspension_hull_shapes"
    };
    for(int i=0;i<SSR_NAME_COUNT;++i){
        if(!ssr_names[i]){ssr_names[i]=PyUnicode_InternFromString(texts[i]);if(!ssr_names[i])return 0;}
    }
    if(!ssr_zero_index){ssr_zero_index=PyLong_FromLong(0);if(!ssr_zero_index)return 0;}
    return 1;
}

/* 逐值核对已有签名；未改变时不再分配各形状数组、矩阵和整份签名。 */
static int support_signature_same(PyObject *old,PyObject *body,PyObject *shapes,PyObject *mesh,
                                 PyObject *bounds,PyObject *vertices,PyObject *net_pose,PyObject **body_mat_out,
                                 PyObject *convex_type,PyObject *bounds_function) {
    if(!PyTuple_Check(old)||PyTuple_GET_SIZE(old)!=10)return 0;
    PyObject *old_shapes=PyTuple_GET_ITEM(old,1);
    if(shapes!=old_shapes){
        int same=PyObject_RichCompareBool(old_shapes,shapes,Py_EQ);if(same<=0)return same;
    }
    const int indices[]={4,5,7};PyObject *tags[]={mesh,bounds,vertices};
    for(int i=0;i<3;++i){PyObject *saved=PyTuple_GET_ITEM(old,indices[i]);
        if(!PyLong_Check(saved))return 0;
        void *pointer=PyLong_AsVoidPtr(saved);if(PyErr_Occurred())return -1;
        if(pointer!=(void *)tags[i])return 0;}
    int pose_same=PyObject_RichCompareBool(net_pose,PyTuple_GET_ITEM(old,8),Py_EQ);if(pose_same<0)return -1;
    if(!pose_same){
        PyObject *mat=PyObject_CallMethodNoArgs(net_pose,ssr_names[SSR_MAT]);if(!mat)return -1;
        *body_mat_out=mat;
        int mat_same=PyObject_RichCompareBool(mat,PyTuple_GET_ITEM(old,0),Py_EQ);if(mat_same<=0)return mat_same;
    }
    Py_ssize_t count=PyTuple_GET_SIZE(shapes);
    PyObject *mats=PyTuple_GET_ITEM(old,2),*margins=PyTuple_GET_ITEM(old,3);
    PyObject *mutable=PyTuple_GET_ITEM(old,6),*poses=PyTuple_GET_ITEM(old,9);
    if(!PyTuple_Check(mats)||!PyTuple_Check(margins)||!PyTuple_Check(mutable)||!PyTuple_Check(poses)
       ||PyTuple_GET_SIZE(mats)!=count||PyTuple_GET_SIZE(margins)!=count
       ||PyTuple_GET_SIZE(mutable)!=count||PyTuple_GET_SIZE(poses)!=count)return 0;
    for(Py_ssize_t j=0;j<count;++j){
        PyObject *index=(j==0)?Py_NewRef(ssr_zero_index):PyLong_FromSsize_t(j);if(!index)return -1;
        PyObject *pose=PyObject_CallMethodOneArg(body,ssr_names[SSR_SHAPE_POSE],index);Py_DECREF(index);if(!pose)return -1;
        int same=PyObject_RichCompareBool(pose,PyTuple_GET_ITEM(poses,j),Py_EQ);
        if(same<0){Py_DECREF(pose);return -1;}
        if(!same){
            PyObject *mat=PyObject_CallMethodNoArgs(pose,ssr_names[SSR_MAT]);Py_DECREF(pose);if(!mat)return -1;
            same=PyObject_RichCompareBool(mat,PyTuple_GET_ITEM(mats,j),Py_EQ);Py_DECREF(mat);if(same<=0)return same;
        } else {
            Py_DECREF(pose);
        }
        PyObject *shape=PyTuple_GET_ITEM(shapes,j);
        PyObject *margin=PyObject_CallMethodNoArgs(shape,ssr_names[SSR_MARGIN]);if(!margin)return -1;
        same=PyObject_RichCompareBool(margin,PyTuple_GET_ITEM(margins,j),Py_EQ);Py_DECREF(margin);if(same<=0)return same;
        int convex=bounds==Py_None?PyObject_IsInstance(shape,convex_type):0;if(convex<0)return -1;
        PyObject *actual=convex?PyObject_CallFunctionObjArgs(bounds_function,shape,Py_None,NULL):Py_NewRef(Py_None);
        if(!actual)return -1;
        same=PyObject_RichCompareBool(actual,PyTuple_GET_ITEM(mutable,j),Py_EQ);Py_DECREF(actual);if(same<=0)return same;
    }
    return 1;
}

static PyObject *static_support_read(PyObject *self,PyObject *args) {
    PyObject *world,*chassis,*mask,*cache,*node_path,*types,*unit_scale,*bounds_function;
    if(!PyArg_ParseTuple(args,"OOOOOOOO",&world,&chassis,&mask,&cache,&node_path,&types,&unit_scale,&bounds_function))return NULL;
    if((cache!=Py_None&&!PyDict_Check(cache))||!PyTuple_Check(types)||PyTuple_GET_SIZE(types)!=4){
        PyErr_SetString(PyExc_TypeError,"静态缓存须为字典，形状类型须为四元组");return NULL;}
    if(!ssr_init_names())return NULL;
    PyObject *bodies=NULL,*ordered=NULL,*groups=NULL,*hulls=NULL,*updates=NULL,*active=NULL;
    PyObject *v[15]={0},*shape_mats=NULL,*mutable_bounds=NULL,*signature=NULL;
    v[0]=PyObject_CallMethodNoArgs(mask,ssr_names[SSR_WORD]);if(!v[0])goto failed;
    unsigned long long mask_word=PyLong_AsUnsignedLongLong(v[0]);Py_CLEAR(v[0]);
    if(mask_word==(unsigned long long)-1&&PyErr_Occurred())goto failed;
    bodies=PyObject_CallMethodNoArgs(world,ssr_names[SSR_BODIES]);if(!bodies)goto failed;
    v[0]=PySequence_Fast(bodies,"世界刚体须为序列");if(!v[0])goto failed;
    ordered=PyList_New(0);if(!ordered)goto failed;
    for(Py_ssize_t i=0;i<PySequence_Fast_GET_SIZE(v[0]);++i){PyObject *body=PySequence_Fast_GET_ITEM(v[0],i);
        int different=PyObject_RichCompareBool(body,chassis,Py_NE);if(different<0)goto failed;if(!different)continue;
        v[1]=PyObject_CallMethodNoArgs(body,ssr_names[SSR_STATIC]);if(!v[1])goto failed;
        int is_static=PyObject_IsTrue(v[1]);Py_CLEAR(v[1]);if(is_static<0)goto failed;if(!is_static)continue;
        v[1]=PyObject_CallMethodNoArgs(body,ssr_names[SSR_MASK]);if(!v[1])goto failed;
        v[2]=PyObject_CallMethodNoArgs(v[1],ssr_names[SSR_WORD]);Py_CLEAR(v[1]);if(!v[2])goto failed;
        unsigned long long body_word=PyLong_AsUnsignedLongLong(v[2]);Py_CLEAR(v[2]);
        if(body_word==(unsigned long long)-1&&PyErr_Occurred())goto failed;
        if((body_word&mask_word)==0)continue;
        v[1]=PyObject_CallMethodNoArgs(body,ssr_names[SSR_NAME]);
        v[2]=PyObject_CallMethodNoArgs(body,ssr_names[SSR_TRANSFORM]);
        if(!v[1]||!v[2])goto failed;
        v[3]=PyObject_CallMethodNoArgs(v[2],ssr_names[SSR_POS]);if(!v[3])goto failed;
        v[4]=PySequence_Tuple(v[3]);Py_CLEAR(v[3]);if(!v[4])goto failed;
        /* 原始索引只在名称/位置相同的情况下保持原稳定排序，不比较刚体对象。 */
        v[3]=Py_BuildValue("OOnOO",v[1],v[4],i,body,v[2]);
        Py_CLEAR(v[1]);Py_CLEAR(v[2]);Py_CLEAR(v[4]);if(!v[3])goto failed;
        if(PyList_Append(ordered,v[3])<0)goto failed;Py_CLEAR(v[3]);
    }
    Py_CLEAR(v[0]);if(PyList_Sort(ordered)<0)goto failed;
    groups=PyList_New(PyList_GET_SIZE(ordered));hulls=PyDict_New();updates=PyList_New(0);active=PySet_New(NULL);
    if(!groups||!hulls||!updates||!active)goto failed;
    for(Py_ssize_t i=0;i<PyList_GET_SIZE(ordered);++i){
        PyObject *entry=PyList_GET_ITEM(ordered,i);
        PyObject *body=PyTuple_GET_ITEM(entry,3);
        PyObject *body_transform=PyTuple_GET_ITEM(entry,4);
        if(PySet_Add(active,body)<0)goto failed;
        PyObject *previous=cache==Py_None?NULL:PyDict_GetItemWithError(cache,body);if(!previous&&PyErr_Occurred())goto failed;
        if(previous&&(!PyTuple_Check(previous)||PyTuple_GET_SIZE(previous)!=3)){
            PyErr_SetString(PyExc_ValueError,"静态缓存记录须含签名/几何/凸体");goto failed;}
        /* 单形状缓存命中直接核对唯一形状，免去每拍构造形状列表与元组。 */
        if(previous&&PyTuple_Check(PyTuple_GET_ITEM(previous,0))&&PyTuple_GET_SIZE(PyTuple_GET_ITEM(previous,0))==10
           &&PyTuple_Check(PyTuple_GET_ITEM(PyTuple_GET_ITEM(previous,0),1))){
            PyObject *old_shapes=PyTuple_GET_ITEM(PyTuple_GET_ITEM(previous,0),1);
            v[0]=PyObject_CallMethodNoArgs(body,ssr_names[SSR_NUM_SHAPES]);if(!v[0])goto failed;
            Py_ssize_t nshapes=PyLong_AsSsize_t(v[0]);Py_CLEAR(v[0]);if(nshapes==-1&&PyErr_Occurred())goto failed;
            if(nshapes==1&&PyTuple_GET_SIZE(old_shapes)==1){
                v[0]=PyObject_CallMethodOneArg(body,ssr_names[SSR_GET_SHAPE],ssr_zero_index);if(!v[0])goto failed;
                int same=PyObject_RichCompareBool(v[0],PyTuple_GET_ITEM(old_shapes,0),Py_EQ);
                if(same<0)goto failed;
                v[1]=same?Py_NewRef(old_shapes):PyTuple_Pack(1,v[0]);
                Py_CLEAR(v[0]);if(!v[1])goto failed;
            } else {
                v[0]=PyObject_CallMethodNoArgs(body,ssr_names[SSR_SHAPES]);if(!v[0])goto failed;
                v[1]=PySequence_Tuple(v[0]);Py_CLEAR(v[0]);if(!v[1])goto failed;
            }
        } else {
            v[0]=PyObject_CallMethodNoArgs(body,ssr_names[SSR_SHAPES]);if(!v[0])goto failed;
            v[1]=PySequence_Tuple(v[0]);Py_CLEAR(v[0]);if(!v[1])goto failed;
        }
        Py_ssize_t count=PyTuple_GET_SIZE(v[1]);
        v[2]=support_read_tag(body,ssr_names[SSR_HAS_TAG],ssr_names[SSR_GET_TAG],ssr_names[SSR_MESH_TAG]);
        v[3]=support_read_tag(body,ssr_names[SSR_HAS_TAG],ssr_names[SSR_GET_TAG],ssr_names[SSR_BOUNDS_TAG]);if(!v[2]||!v[3])goto failed;
        v[4]=PyObject_CallMethodNoArgs(body,ssr_names[SSR_NUM_PARENTS]);if(!v[4])goto failed;
        Py_ssize_t nparents=PyLong_AsSsize_t(v[4]);Py_CLEAR(v[4]);if(nparents==-1&&PyErr_Occurred())goto failed;
        if(nparents==0){
            v[5]=Py_NewRef(body_transform);
        } else {
            v[4]=PyObject_CallOneArg(node_path,body);if(!v[4])goto failed;
            v[5]=PyObject_CallMethodNoArgs(v[4],ssr_names[SSR_NET]);Py_CLEAR(v[4]);if(!v[5])goto failed;
        }
        v[8]=PyObject_CallMethodOneArg(body,ssr_names[SSR_HAS_TAG],ssr_names[SSR_VERTICES_TAG]);if(!v[8])goto failed;
        int has_vertices=PyObject_IsTrue(v[8]);Py_CLEAR(v[8]);if(has_vertices<0)goto failed;
        v[10]=Py_NewRef(Py_None);
        if(has_vertices){v[8]=PyObject_CallMethodOneArg(body,ssr_names[SSR_GET_TAG],ssr_names[SSR_HULLS_TAG]);if(!v[8])goto failed;
            int same=PyObject_RichCompareBool(v[1],v[8],Py_EQ);Py_CLEAR(v[8]);if(same<0)goto failed;
            if(same){v[8]=PyObject_CallMethodNoArgs(v[5],ssr_names[SSR_SCALE]);if(!v[8])goto failed;
                int unit=PyObject_RichCompareBool(v[8],unit_scale,Py_EQ);Py_CLEAR(v[8]);if(unit<0)goto failed;
                if(unit){Py_CLEAR(v[10]);v[10]=PyObject_CallMethodOneArg(body,ssr_names[SSR_GET_TAG],ssr_names[SSR_VERTICES_TAG]);if(!v[10])goto failed;}}}
        if(previous){
            int same=support_signature_same(PyTuple_GET_ITEM(previous,0),body,v[1],v[2],v[3],v[10],v[5],&v[11],
                                            PyTuple_GET_ITEM(types,3),bounds_function);
            if(same<0)goto failed;
            if(same){PyList_SET_ITEM(groups,i,Py_NewRef(PyTuple_GET_ITEM(previous,1)));
                if(PyTuple_GET_ITEM(previous,2)!=Py_None&&PyDict_SetItem(hulls,body,PyTuple_GET_ITEM(previous,2))<0)goto failed;
                for(int j=0;j<15;++j)Py_CLEAR(v[j]);continue;}}
        if(!v[11]){v[11]=PyObject_CallMethodNoArgs(v[5],ssr_names[SSR_MAT]);if(!v[11])goto failed;}
        int supported=count!=0;
        for(Py_ssize_t j=0;j<count&&supported;++j){PyObject *shape=PyTuple_GET_ITEM(v[1],j);
            int box=PyObject_IsInstance(shape,PyTuple_GET_ITEM(types,0));if(box<0)goto failed;
            int plane=box?0:PyObject_IsInstance(shape,PyTuple_GET_ITEM(types,1));if(plane<0)goto failed;
            int mesh=(box||plane)?0:PyObject_IsInstance(shape,PyTuple_GET_ITEM(types,2));if(mesh<0)goto failed;
            supported=box||plane||(mesh&&v[2]!=Py_None&&count==1);}
        v[6]=PyTuple_New(count);v[7]=PyTuple_New(count);shape_mats=PyTuple_New(count);mutable_bounds=PyTuple_New(count);
        if(!v[6]||!v[7]||!shape_mats||!mutable_bounds)goto failed;
        for(Py_ssize_t j=0;j<count;++j){PyObject *shape=PyTuple_GET_ITEM(v[1],j);
            v[8]=(j==0)?Py_NewRef(ssr_zero_index):PyLong_FromSsize_t(j);if(!v[8])goto failed;
            v[9]=PyObject_CallMethodOneArg(body,ssr_names[SSR_SHAPE_POSE],v[8]);Py_CLEAR(v[8]);if(!v[9])goto failed;
            v[8]=PyObject_CallMethodNoArgs(v[9],ssr_names[SSR_MAT]);if(!v[8])goto failed;
            PyTuple_SET_ITEM(shape_mats,j,v[8]);v[8]=NULL;PyTuple_SET_ITEM(v[6],j,v[9]);v[9]=NULL;
            v[8]=PyObject_CallMethodNoArgs(shape,ssr_names[SSR_MARGIN]);if(!v[8])goto failed;
            PyTuple_SET_ITEM(v[7],j,v[8]);v[8]=NULL;
            int convex=v[3]==Py_None?PyObject_IsInstance(shape,PyTuple_GET_ITEM(types,3)):0;if(convex<0)goto failed;
            v[8]=convex?PyObject_CallFunctionObjArgs(bounds_function,shape,Py_None,NULL):Py_NewRef(Py_None);
            if(!v[8])goto failed;PyTuple_SET_ITEM(mutable_bounds,j,v[8]);v[8]=NULL;
        }
        v[12]=PyLong_FromVoidPtr(v[2]);v[13]=PyLong_FromVoidPtr(v[3]);v[14]=PyLong_FromVoidPtr(v[10]);
        if(!v[12]||!v[13]||!v[14])goto failed;
        signature=PyTuple_Pack(10,v[11],v[1],shape_mats,v[7],v[12],v[13],mutable_bounds,v[14],v[5],v[6]);if(!signature)goto failed;
        PyList_SET_ITEM(groups,i,Py_NewRef(Py_None));
        PyObject *record=Py_BuildValue("nOOOOOOOOO",i,body,supported?Py_True:Py_False,v[1],v[2],v[3],v[5],v[6],v[7],v[10]);
        if(!record)goto failed;
        PyObject *update=PyTuple_Pack(2,record,signature);Py_DECREF(record);if(!update)goto failed;
        int appended=PyList_Append(updates,update);Py_DECREF(update);if(appended<0)goto failed;
        for(int j=0;j<15;++j)Py_CLEAR(v[j]);Py_CLEAR(shape_mats);Py_CLEAR(mutable_bounds);Py_CLEAR(signature);
    }
    if(cache!=Py_None){v[0]=PyDict_Keys(cache);if(!v[0])goto failed;
        for(Py_ssize_t i=0;i<PyList_GET_SIZE(v[0]);++i){PyObject *body=PyList_GET_ITEM(v[0],i);
            int present=PySet_Contains(active,body);if(present<0)goto failed;
            if(!present&&PyDict_DelItem(cache,body)<0)goto failed;}Py_CLEAR(v[0]);}
    PyObject *result=PyTuple_Pack(3,groups,hulls,updates);
    Py_DECREF(bodies);Py_DECREF(ordered);Py_DECREF(groups);
    Py_DECREF(hulls);Py_DECREF(updates);Py_DECREF(active);return result;
failed:
    for(int i=0;i<15;++i)Py_XDECREF(v[i]);
    Py_XDECREF(bodies);Py_XDECREF(ordered);Py_XDECREF(groups);Py_XDECREF(hulls);Py_XDECREF(updates);Py_XDECREF(active);
    Py_XDECREF(shape_mats);Py_XDECREF(mutable_bounds);Py_XDECREF(signature);return NULL;
}
