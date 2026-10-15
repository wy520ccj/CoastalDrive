/* 四轮原行程/轮轴、实际命中后的初始材料状态与共轭梯度连续装配。 */
enum {S_TRAVEL,S_RADIUS,S_WIDTH,S_SHOULDER,S_CROWN,S_REST,S_STEER,S_STATIC,S_POINT,S_NORMAL,S_FRACTION,S_NODE,S_KEY_COUNT};
static PyObject *suspension_keys[S_KEY_COUNT];
static PyObject *suspension_identity;
static int suspension_keys_init(void) {
    const char *names[]={"suspension_travel","wheel_radius","wheel_width","wheel_shoulder_radius","wheel_crown_height",
        "getSuspensionRestLength","getSteering","isStatic","point","normal","fraction","node"};
    for(int i=0;i<S_KEY_COUNT;++i){suspension_keys[i]=PyUnicode_InternFromString(names[i]);if(!suspension_keys[i])return 0;}
    suspension_identity=Py_BuildValue("((ddd)(ddd)(ddd))",1.,0.,0.,0.,1.,0.,0.,0.,1.);return suspension_identity!=NULL;
}
static PyObject *suspension_field(PyObject *dict,int key) {
    PyObject *value=PyDict_GetItemWithError(dict,suspension_keys[key]);
    if(!value&&!PyErr_Occurred())PyErr_SetObject(PyExc_KeyError,suspension_keys[key]);return value;
}
static int suspension_number(PyObject *dict,int key,double *value) {
    PyObject *item=suspension_field(dict,key);if(!item)return 0;*value=PyFloat_AsDouble(item);return !PyErr_Occurred();
}
static PyObject *suspension_prepare_paths(PyObject *self,PyObject *args) {
    PyObject *wheels,*config,*origin_object,*direction_object,*arms,*right_object,*forward_object;
    if(!PyArg_ParseTuple(args,"OOOOOOO",&wheels,&config,&origin_object,&direction_object,&arms,&right_object,&forward_object))return NULL;
    PyObject *sequence=PySequence_Fast(wheels,"悬架须有四轮硬件"),*settings=PyObject_GenericGetDict(config,NULL),
        *rests=PyTuple_New(4),*lengths=PyTuple_New(4),*axes=PyTuple_New(4),*rays=PyTuple_New(4),*rest=NULL,*steering=NULL;
    double origin[3],direction[3],right[3],forward[3],radius,travel;
    if(!sequence||!settings||!rests||!lengths||!axes||!rays)goto failed;
    if(PySequence_Fast_GET_SIZE(sequence)!=4||!control_four(arms)){
        if(!PyErr_Occurred())PyErr_SetString(PyExc_ValueError,"悬架须有四轮硬件");goto failed;}
    if(!vector(origin_object,origin)||!vector(direction_object,direction)||!vector(right_object,right)||!vector(forward_object,forward)
        ||!suspension_number(settings,S_RADIUS,&radius)||!suspension_number(settings,S_TRAVEL,&travel))goto failed;
    for(int i=0;i<4;++i){PyObject *wheel=PySequence_Fast_GET_ITEM(sequence,i);double hub[3],axis[3],start[3],end[3],terms[3];
        rest=PyObject_CallMethodNoArgs(wheel,suspension_keys[S_REST]);
        steering=PyObject_CallMethodNoArgs(wheel,suspension_keys[S_STEER]);
        if(!rest||!steering||!vector(PyTuple_GET_ITEM(arms,i),hub))goto failed;
        double reach=PyFloat_AsDouble(rest)+travel+radius;
        double theta=-PyFloat_AsDouble(steering)*(3.141592653589793238462643383279502884197/180.0);
        if(PyErr_Occurred())goto failed;
        if(isinf(theta)){PyErr_SetString(PyExc_ValueError,"math domain error");goto failed;}
        double cosine=cos(theta),sine=sin(theta);
        for(int a=0;a<3;++a){axis[a]=cosine*right[a]-sine*forward[a];terms[a]=axis[a]*axis[a];
            start[a]=origin[a]+hub[a]-direction[a]*radius;end[a]=start[a]+direction[a]*reach;}
        double magnitude=sqrt(sum_three(terms));if(magnitude==0.){PyErr_SetString(PyExc_ZeroDivisionError,"float division by zero");goto failed;}
        for(int a=0;a<3;++a)axis[a]/=magnitude;
        PyTuple_SET_ITEM(rests,i,rest);rest=NULL;
        PyTuple_SET_ITEM(lengths,i,PyFloat_FromDouble(reach));
        PyTuple_SET_ITEM(axes,i,Py_BuildValue("(ddd)",axis[0],axis[1],axis[2]));
        PyTuple_SET_ITEM(rays,i,Py_BuildValue("((ddd)(ddd))",start[0],start[1],start[2],end[0],end[1],end[2]));
        if(!PyTuple_GET_ITEM(lengths,i)||!PyTuple_GET_ITEM(axes,i)||!PyTuple_GET_ITEM(rays,i))goto failed;Py_CLEAR(steering);
    }
    Py_DECREF(sequence);Py_DECREF(settings);return Py_BuildValue("NNNN",rests,lengths,axes,rays);
failed:
    Py_XDECREF(sequence);Py_XDECREF(settings);Py_XDECREF(rests);Py_XDECREF(lengths);Py_XDECREF(axes);Py_XDECREF(rays);
    Py_XDECREF(rest);Py_XDECREF(steering);return NULL;
}
static PyObject *suspension_prepare_system(PyObject *self,PyObject *args) {
    PyObject *config,*compression,*previous_tick,*previous_force,*geometry_values,*context,*types;
    if(!PyArg_ParseTuple(args,"OOOOOOO",&config,&compression,&previous_tick,&previous_force,&geometry_values,&context,&types))return NULL;
    if(!control_four(compression)||!control_four(previous_force))return NULL;
    PyObject *origin_object=PyTuple_GET_ITEM(geometry_values,0),*direction_object=PyTuple_GET_ITEM(geometry_values,1),
        *arms=PyTuple_GET_ITEM(geometry_values,2),*axes=PyTuple_GET_ITEM(geometry_values,3),*lengths=PyTuple_GET_ITEM(geometry_values,4),
        *rests=PyTuple_GET_ITEM(geometry_values,5),*hits=PyTuple_GET_ITEM(geometry_values,6);
    PyObject *world=PyTuple_GET_ITEM(context,0),*chassis=PyTuple_GET_ITEM(context,1),*envelope=PyTuple_GET_ITEM(context,2),
        *static_shapes=PyTuple_GET_ITEM(context,3),*candidates=PyTuple_GET_ITEM(context,4),*damping=PyTuple_GET_ITEM(context,5);
    PyObject *settings=PyObject_GenericGetDict(config,NULL),*geometry=PyTuple_New(4),*initial=PyTuple_New(4),
        *constraint=PyTuple_New(4),*gradients=PyTuple_New(4),*touching=PyTuple_New(4),*alignments=PyTuple_New(4),*planes=PyTuple_New(4),
        *identity=Py_NewRef(suspension_identity),*empty=PyTuple_New(0),
        *hit_values=NULL,*alignment_object=NULL,*arm_object=NULL,*surface=NULL,*plane=NULL,*static_result=NULL;
    double origin[3],direction[3],radius;
    int initialized=PyObject_IsTrue(previous_tick);if(initialized<0)goto failed;
    if(!settings||!geometry||!initial||!constraint||!gradients||!touching||!alignments||!planes||!identity||!empty)goto failed;
    /* 新元组逐轮替换，不能原位修改调用方的上拍压缩量。 */
    for(int i=0;i<4;++i){PyTuple_SET_ITEM(initial,i,Py_NewRef(PyTuple_GET_ITEM(compression,i)));
        PyTuple_SET_ITEM(constraint,i,Py_NewRef(PyTuple_GET_ITEM(compression,i)));}
    if(!vector(origin_object,origin)||!vector(direction_object,direction)
        ||!suspension_number(settings,S_RADIUS,&radius))goto failed;
    for(int i=0;i<4;++i){PyObject *hit=PyTuple_GET_ITEM(hits,i),*point=Py_None,*normal=Py_None,*rest=PyTuple_GET_ITEM(rests,i);
        double alignment=0.,arm[3],normal_values[3];int eligible=0;
        alignment_object=Py_NewRef(Py_None);
        if(hit!=Py_None){hit_values=PyObject_GenericGetDict(hit,NULL);if(!hit_values)goto failed;
            point=suspension_field(hit_values,S_POINT);normal=suspension_field(hit_values,S_NORMAL);
            if(!point||!normal||!vector(normal,normal_values))goto failed;alignment=-dot(normal_values,direction);
            Py_SETREF(alignment_object,PyFloat_FromDouble(alignment));if(!alignment_object)goto failed;
            PyObject *node=suspension_field(hit_values,S_NODE);if(!node)goto failed;
            static_result=PyObject_CallMethodNoArgs(node,suspension_keys[S_STATIC]);if(!static_result)goto failed;
            int fixed=PyObject_IsTrue(static_result);if(fixed<0)goto failed;eligible=fixed&&alignment>0.;Py_CLEAR(static_result);
        }
        PyObject *gradient=Py_BuildValue("(dddddd)",0.,0.,0.,0.,0.,0.);if(!gradient)goto failed;
        PyTuple_SET_ITEM(gradients,i,gradient);
        if(eligible){double rest_length=PyFloat_AsDouble(rest),ray_length=PyFloat_AsDouble(PyTuple_GET_ITEM(lengths,i)),fraction;
            if(PyErr_Occurred()||!suspension_number(hit_values,S_FRACTION,&fraction))goto failed;
            double current=rest_length-(ray_length*fraction-radius),old_force=PyFloat_AsDouble(PyTuple_GET_ITEM(previous_force,i));
            if(PyErr_Occurred())goto failed;
            PyObject *value=PyFloat_FromDouble(current);if(!value)goto failed;
            Py_DECREF(PyTuple_GET_ITEM(constraint,i));PyTuple_SET_ITEM(constraint,i,value);
            if(!initialized||old_force>0.){value=PyFloat_FromDouble(!initialized&&!(current>0.)?0.:current);if(!value)goto failed;
                Py_DECREF(PyTuple_GET_ITEM(initial,i));PyTuple_SET_ITEM(initial,i,value);}
            if(!vector(point,arm))goto failed;for(int a=0;a<3;++a)arm[a]-=origin[a];
            double torque[3];publish_cross(arm,normal_values,torque);
            value=Py_BuildValue("(dddddd)",normal_values[0]/alignment,normal_values[1]/alignment,normal_values[2]/alignment,
                torque[0]/alignment,torque[1]/alignment,torque[2]/alignment);if(!value)goto failed;
            Py_DECREF(PyTuple_GET_ITEM(gradients,i));PyTuple_SET_ITEM(gradients,i,value);
            arm_object=Py_BuildValue("(ddd)",arm[0],arm[1],arm[2]);if(!arm_object)goto failed;
            PyObject *zero=PyFloat_FromDouble(0.),*reach=PyNumber_Add(rest,suspension_field(settings,S_TRAVEL));
            if(!zero||!reach){Py_XDECREF(zero);Py_XDECREF(reach);goto failed;}
            surface=PyObject_CallFunctionObjArgs(PyTuple_GET_ITEM(types,0),empty,zero,identity,origin_object,
                suspension_field(settings,S_RADIUS),reach,suspension_field(settings,S_WIDTH),suspension_field(settings,S_SHOULDER),
                PyTuple_GET_ITEM(axes,i),Py_None,suspension_field(settings,S_CROWN),Py_None,world,chassis,envelope,static_shapes,NULL);
            Py_DECREF(zero);Py_DECREF(reach);
            if(!surface)goto failed;
            PyObject *cache=PyObject_GetAttrString(surface,"candidates");if(!cache)goto failed;
            int copied=PyDict_Update(cache,candidates);Py_DECREF(cache);if(copied<0)goto failed;
            PyObject *normal_tuple=PySequence_Tuple(normal);value=PyFloat_FromDouble(rest_length-current);
            if(!normal_tuple||!value){Py_XDECREF(normal_tuple);Py_XDECREF(value);goto failed;}
            plane=PyObject_CallFunctionObjArgs(PyTuple_GET_ITEM(types,1),PyTuple_GET_ITEM(arms,i),direction_object,normal_tuple,
                value,surface,arm_object,NULL);Py_DECREF(normal_tuple);Py_DECREF(value);if(!plane)goto failed;
        }else plane=Py_NewRef(Py_None);
        PyObject *row=PyTuple_Pack(4,point,normal,alignment_object,rest);if(!row)goto failed;
        PyTuple_SET_ITEM(geometry,i,row);PyTuple_SET_ITEM(touching,i,Py_NewRef(eligible?Py_True:Py_False));
        PyTuple_SET_ITEM(alignments,i,alignment_object);alignment_object=NULL;PyTuple_SET_ITEM(planes,i,plane);plane=NULL;
        Py_CLEAR(hit_values);Py_CLEAR(surface);Py_CLEAR(arm_object);
    }
    PyObject *system=PyObject_CallFunctionObjArgs(PyTuple_GET_ITEM(types,2),initial,constraint,gradients,touching,alignments,config,planes,damping,NULL);
    if(!system)goto failed;
    Py_DECREF(settings);Py_DECREF(initial);Py_DECREF(constraint);Py_DECREF(gradients);Py_DECREF(touching);Py_DECREF(alignments);
    Py_DECREF(planes);Py_DECREF(identity);Py_DECREF(empty);return Py_BuildValue("NN",geometry,system);
failed:
    Py_XDECREF(settings);Py_XDECREF(geometry);Py_XDECREF(initial);Py_XDECREF(constraint);Py_XDECREF(gradients);Py_XDECREF(touching);
    Py_XDECREF(alignments);Py_XDECREF(planes);Py_XDECREF(identity);Py_XDECREF(empty);Py_XDECREF(hit_values);Py_XDECREF(alignment_object);
    Py_XDECREF(arm_object);Py_XDECREF(surface);Py_XDECREF(plane);Py_XDECREF(static_result);return NULL;
}
