/* Panda真实接点给定后，四轮双精度正交基、响应矩阵与完整记录一次准备。 */
enum {F_HUB,F_MOBILITY,F_ELASTIC,F_RX,F_RY,F_RT,F_SPIN,F_RADIUS,F_MOMENT,F_XX,F_XY,F_XT,F_YY,F_YT,F_TT,F_KEY_COUNT};
static PyObject *frame_keys[F_KEY_COUNT];
static int frame_keys_init(void) {
    const char *names[]={"hub","mobility","elastic_frame","response_x","response_y","response_t","spin_axis","rolling_radius",
        "moment_x","xx","xy","xt","yy","yt","tt"};
    for(int i=0;i<F_KEY_COUNT;++i){frame_keys[i]=PyUnicode_InternFromString(names[i]);if(!frame_keys[i])return 0;}return 1;
}
static PyObject *frame_three(const double values[3]) {return Py_BuildValue("(ddd)",values[0],values[1],values[2]);}
static int frame_put(PyObject *dict,int key,PyObject *value) {return value&&PyDict_SetItem(dict,frame_keys[key],value)==0;}
static int frame_float(PyObject *dict,int key,double value) {
    PyObject *number=PyFloat_FromDouble(value);if(!number)return 0;
    int ok=frame_put(dict,key,number);Py_DECREF(number);return ok;
}
static PyObject *frame_record(PyObject *type,PyObject *values) {
    PyObject *record=PyType_GenericAlloc((PyTypeObject *)type,0);if(!record)return NULL;
    if(PyObject_GenericSetDict(record,values,NULL))Py_CLEAR(record);return record;
}
static PyObject *tire_prepare_frames(PyObject *self,PyObject *args) {
    PyObject *config,*frame_type,*mobility_type,*tensor,*geometry;
    if(!PyArg_ParseTuple(args,"OOOOO",&config,&frame_type,&mobility_type,&tensor,&geometry))return NULL;
    if(!control_four(geometry))return NULL;
    PyObject *hardware=PyObject_GenericGetDict(config,NULL),*frames=PyTuple_New(4),*frame=NULL,*mobility=NULL,
        *elastic=NULL,*responses=NULL,*mx=NULL,*my=NULL,*up_object=NULL,*hub_object=NULL,*point_object=NULL,*mobility_record=NULL;
    double mass,radius,matrix[3][3];
    if(!hardware||!frames||!publish_number(hardware,P_MASS,&mass)||!publish_number(hardware,P_WHEEL_RADIUS,&radius))goto failed;
    for(int a=0;a<3;++a)if(!publish_vector(PyTuple_GET_ITEM(tensor,a),matrix[a]))goto failed;
    for(int i=0;i<4;++i){PyObject *raw=PyTuple_GET_ITEM(geometry,i);
        double tangent[3],up[3],point[3],hub[3],moment_x[3],moment_y[3],axle[3],rx[3],ry[3],rt[3],terms[3];
        if(!publish_vector(PyTuple_GET_ITEM(raw,4),tangent)||!publish_vector(PyTuple_GET_ITEM(raw,5),up)
            ||!publish_vector(PyTuple_GET_ITEM(raw,6),point))goto failed;
        for(int a=0;a<3;++a)terms[a]=up[a]*up[a];double length=sqrt(sum_three(terms));
        if(length==0.){PyErr_SetString(PyExc_ZeroDivisionError,"float division by zero");goto failed;}
        for(int a=0;a<3;++a)up[a]/=length;
        for(int a=0;a<3;++a)terms[a]=tangent[a]*up[a];double projection=sum_three(terms);
        for(int a=0;a<3;++a)tangent[a]-=projection*up[a];
        for(int a=0;a<3;++a)terms[a]=tangent[a]*tangent[a];length=sqrt(sum_three(terms));
        if(length==0.){PyErr_SetString(PyExc_ZeroDivisionError,"float division by zero");goto failed;}
        for(int a=0;a<3;++a)tangent[a]/=length;
        publish_cross(tangent,up,axle);
        for(int a=0;a<3;++a)hub[a]=point[a]+up[a]*radius;
        publish_cross(hub,tangent,moment_x);publish_cross(point,axle,moment_y);
        for(int a=0;a<3;++a){rx[a]=dot(matrix[a],moment_x);ry[a]=dot(matrix[a],moment_y);rt[a]=dot(matrix[a],axle);}
        frame=PyDict_New();mobility=PyDict_New();
        mx=frame_three(tangent);my=frame_three(axle);up_object=frame_three(up);
        point_object=frame_three(point);hub_object=frame_three(hub);
        responses=Py_BuildValue("((ddd)(ddd)(ddd))",rx[0],rx[1],rx[2],ry[0],ry[1],ry[2],rt[0],rt[1],rt[2]);
        if(!frame||!mobility||!mx||!my||!up_object||!point_object||!hub_object||!responses)goto failed;
        elastic=PyTuple_Pack(3,mx,my,up_object);if(!elastic)goto failed;
        if(!frame_float(mobility,F_XX,1/mass+dot(moment_x,rx))||!frame_float(mobility,F_XY,dot(moment_x,ry))
            ||!frame_float(mobility,F_XT,dot(moment_x,rt))||!frame_float(mobility,F_YY,1/mass+dot(moment_y,ry))
            ||!frame_float(mobility,F_YT,dot(moment_y,rt))||!frame_float(mobility,F_TT,dot(axle,rt)))goto failed;
        mobility_record=frame_record(mobility_type,mobility);if(!mobility_record)goto failed;
        if(!publish_put(frame,P_STEERING,PyTuple_GET_ITEM(raw,0))||!publish_put(frame,P_SUPPORTED,PyTuple_GET_ITEM(raw,1))
            ||!publish_put(frame,P_LOAD,PyTuple_GET_ITEM(raw,2))||!publish_put(frame,P_MU,PyTuple_GET_ITEM(raw,3))
            ||!publish_put(frame,P_TANGENT,mx)||!publish_put(frame,P_AXLE,my)||!publish_put(frame,P_POINT,point_object)
            ||!frame_put(frame,F_HUB,hub_object)||!frame_put(frame,F_MOBILITY,mobility_record)||!frame_put(frame,F_ELASTIC,elastic)
            ||!frame_put(frame,F_RX,PyTuple_GET_ITEM(responses,0))||!frame_put(frame,F_RY,PyTuple_GET_ITEM(responses,1))
            ||!frame_put(frame,F_RT,PyTuple_GET_ITEM(responses,2))||!frame_put(frame,F_SPIN,Py_None)
            ||!frame_put(frame,F_RADIUS,Py_None)||!frame_put(frame,F_MOMENT,Py_None))goto failed;
        PyObject *record=frame_record(frame_type,frame);if(!record)goto failed;PyTuple_SET_ITEM(frames,i,record);
        Py_CLEAR(frame);Py_CLEAR(mobility);Py_CLEAR(elastic);Py_CLEAR(mx);Py_CLEAR(my);Py_CLEAR(up_object);Py_CLEAR(hub_object);
        Py_CLEAR(point_object);Py_CLEAR(responses);Py_CLEAR(mobility_record);
    }
    Py_DECREF(hardware);return frames;
failed:
    Py_XDECREF(hardware);Py_XDECREF(frames);Py_XDECREF(frame);Py_XDECREF(mobility);Py_XDECREF(elastic);Py_XDECREF(mx);Py_XDECREF(my);
    Py_XDECREF(up_object);Py_XDECREF(hub_object);Py_XDECREF(point_object);Py_XDECREF(responses);Py_XDECREF(mobility_record);return NULL;
}
