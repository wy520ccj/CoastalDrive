/* 四轮末状态、实际冲量与完整力学账一次装配；不积分车身。 */
enum {P_OMEGA,P_ROTATION,P_RELATIVE_OMEGA,P_LONGITUDINAL_SPEED,P_LATERAL_SPEED,P_KAPPA,P_ALPHA,P_FX,P_FY,P_DRIVE_TORQUE,P_BRAKE_CAPACITY,P_BRAKE_TORQUE,P_NORMAL_LOAD,P_ROAD_SUPPORT,P_STEERING,P_FORCE_CONTACT_TICK,P_FORCE_RESIDUAL,P_FORCE_KAPPA,P_FORCE_ALPHA,P_FORCE_MODE,P_LONGITUDINAL_IMPULSE,P_LATERAL_IMPULSE,P_BRAKE_ANGULAR_IMPULSE,P_FORCE_GRIP,P_FORCE_LONGITUDINAL_STIFFNESS,P_FORCE_LATERAL_STIFFNESS,P_DEFORMATION_X,P_DEFORMATION_Y,P_FORCE_PATCH_KAPPA,P_FORCE_PATCH_ALPHA,P_ELASTIC_ENERGY,P_MATERIAL_DISSIPATION,P_ROAD_DISSIPATION,P_ELASTIC_NUMERICAL_DISSIPATION,P_FRAME_DISSIPATION,P_DEFORMATION_RATE_X,P_DEFORMATION_RATE_Y,P_MECHANICAL_AXIS,P_ROLLING_RADIUS,P_GYRO_ANGULAR_IMPULSE,P_STEERING_ANGULAR_IMPULSE,P_STEERING_WORK,P_LONGITUDINAL_ANGULAR_IMPULSE,P_LATERAL_ANGULAR_IMPULSE,P_ROLLING_TORQUE,P_ROLLING_ANGULAR_IMPULSE,P_ROLLING_DISSIPATION,P_FORCE_ROLLING_RADIUS,P_SUPPORTED,P_LOAD,P_MU,P_TANGENT,P_AXLE,P_POINT,P_ELASTIC_FRAME,P_SPIN_AXIS,P_VX,P_VY,P_RESIDUAL,P_MODE,P_PATCH_KAPPA,P_PATCH_ALPHA,P_GYRO_TORQUE,P_STEERING_TORQUE,P_MASS,P_WHEEL_RADIUS,P_TIRE_PEAK_LOAD_EXPONENT,P_LONGITUDINAL_STIFFNESS,P_LATERAL_STIFFNESS,P_LONGITUDINAL_LOAD_EXPONENT,P_LATERAL_LOAD_EXPONENT,P_WHEEL_ROTOR_TRANSPORT,P_TIRE_COMPLIANCE,P_KEY_COUNT};
static PyObject *publish_keys[P_KEY_COUNT];
static int publish_keys_init(void) {
const char *names[]={"omega","rotation","relative_omega","longitudinal_speed","lateral_speed","kappa","alpha","fx","fy","drive_torque","brake_capacity","brake_torque","normal_load","road_support","steering","force_contact_tick","force_residual","force_kappa","force_alpha","force_mode","longitudinal_impulse","lateral_impulse","brake_angular_impulse","force_grip","force_longitudinal_stiffness","force_lateral_stiffness","deformation_x","deformation_y","force_patch_kappa","force_patch_alpha","elastic_energy","material_dissipation","road_dissipation","elastic_numerical_dissipation","frame_dissipation","deformation_rate_x","deformation_rate_y","mechanical_axis","rolling_radius","gyro_angular_impulse","steering_angular_impulse","steering_work","longitudinal_angular_impulse","lateral_angular_impulse","rolling_torque","rolling_angular_impulse","rolling_dissipation","force_rolling_radius","supported","load","mu","tangent","axle","point","elastic_frame","spin_axis","vx","vy","residual","mode","patch_kappa","patch_alpha","gyro_torque","steering_torque","mass","wheel_radius","tire_peak_load_exponent","longitudinal_stiffness","lateral_stiffness","longitudinal_load_exponent","lateral_load_exponent","wheel_rotor_transport","tire_compliance"};
for(int i=0;i<P_KEY_COUNT;++i){publish_keys[i]=PyUnicode_InternFromString(names[i]);if(!publish_keys[i])return 0;}return 1;
}

static PyObject *publish_field(PyObject *dict,int key) {
    PyObject *value=PyDict_GetItemWithError(dict,publish_keys[key]);
    if(!value&&!PyErr_Occurred())PyErr_SetObject(PyExc_KeyError,publish_keys[key]);return value;
}
static int publish_number(PyObject *dict,int key,double *value) {
    PyObject *item=publish_field(dict,key);if(!item)return 0;
    *value=PyFloat_AsDouble(item);return !PyErr_Occurred();
}
static int publish_put(PyObject *dict,int key,PyObject *value) {
    return value&&PyDict_SetItem(dict,publish_keys[key],value)==0;
}
static int publish_float(PyObject *dict,int key,double value) {
    PyObject *number=PyFloat_FromDouble(value);if(!number)return 0;
    int ok=publish_put(dict,key,number);Py_DECREF(number);return ok;
}
static int publish_copy(PyObject *out,int target,PyObject *in,int source) {
    return publish_put(out,target,publish_field(in,source));
}
static int publish_accumulate(PyObject *out,int key,PyObject *old,int source,double delta,int accumulate) {
    double previous=0.;if(accumulate&&!publish_number(old,source,&previous))return 0;
    return publish_float(out,key,previous+delta);
}
static int publish_vector(PyObject *value,double out[3]) {
    PyObject *seq=PySequence_Fast(value,"轮端向量须为序列");if(!seq)return 0;
    if(PySequence_Fast_GET_SIZE(seq)!=3){Py_DECREF(seq);PyErr_SetString(PyExc_ValueError,"轮端向量须为三维");return 0;}
    for(int a=0;a<3;++a){out[a]=PyFloat_AsDouble(PySequence_Fast_GET_ITEM(seq,a));if(PyErr_Occurred()){Py_DECREF(seq);return 0;}}
    Py_DECREF(seq);return 1;
}
static int publish_three(PyObject *out,int key,const double values[3]) {
    PyObject *value=Py_BuildValue("(ddd)",values[0],values[1],values[2]);if(!value)return 0;
    int ok=publish_put(out,key,value);Py_DECREF(value);return ok;
}
static void publish_cross(const double a[3],const double b[3],double out[3]) {
    out[0]=a[1]*b[2]-a[2]*b[1];out[1]=a[2]*b[0]-a[0]*b[2];out[2]=a[0]*b[1]-a[1]*b[0];
}
static int publish_impulse(PyObject *out,const char *kind,const double vector[3],const double *point) {
    PyObject *item=point?Py_BuildValue("(s(ddd)(ddd))",kind,vector[0],vector[1],vector[2],point[0],point[1],point[2])
                        :Py_BuildValue("(s(ddd)O)",kind,vector[0],vector[1],vector[2],Py_None);
    if(!item)return 0;int ok=PyList_Append(out,item)==0;Py_DECREF(item);return ok;
}
static PyObject *tire_publish(PyObject *self,PyObject *args) {
    PyObject *empty,*config,*rear,*frames,*steps,*previous,*rotation,*deformation,*drives,*capacities,*losses,*angular,*tick;
    double dt;int accumulate,reverse;
    if(!PyArg_ParseTuple(args,"OOOOOOOOOOOOdOpp",&empty,&config,&rear,&frames,&steps,&previous,&rotation,
        &deformation,&drives,&capacities,&losses,&angular,&dt,&tick,&accumulate,&reverse))return NULL;
    if(!control_four(frames)||!control_four(steps)||!control_four(previous)||!control_four(rotation)
        ||!control_four(deformation)||!control_four(drives)||!control_four(capacities)||!control_four(losses))return NULL;
    PyObject *hardware=PyObject_GenericGetDict(config,NULL),*rear_hardware=PyObject_GenericGetDict(rear,NULL);
    PyObject *defaults=PyObject_GenericGetDict(empty,NULL),*states=PyTuple_New(4),*angles=PyTuple_New(4),*omegas=PyTuple_New(4),
             *elastic=PyTuple_New(4),*impulses=PyList_New(0),*frame=NULL,*step=NULL,*old=NULL,*values=NULL;
    double end_angular[3],mass,radius,peak;int rotor,compliance;
    if(!hardware||!rear_hardware||!defaults||!states||!angles||!omegas||!elastic||!impulses)goto failed;
    if(!publish_vector(angular,end_angular)||!publish_number(hardware,P_MASS,&mass)||!publish_number(hardware,P_WHEEL_RADIUS,&radius)
        ||!publish_number(hardware,P_TIRE_PEAK_LOAD_EXPONENT,&peak))goto failed;
    rotor=PyObject_IsTrue(publish_field(hardware,P_WHEEL_ROTOR_TRANSPORT));
    compliance=PyObject_IsTrue(publish_field(hardware,P_TIRE_COMPLIANCE));if(rotor<0||compliance<0)goto failed;
    for(int order=0;order<4;++order){int i=reverse?3-order:order;
        frame=PyObject_GenericGetDict(PyTuple_GET_ITEM(frames,i),NULL);
        step=PyObject_GenericGetDict(PyTuple_GET_ITEM(steps,i),NULL);
        old=PyObject_GenericGetDict(PyTuple_GET_ITEM(previous,i),NULL);values=PyDict_Copy(defaults);
        if(!frame||!step||!old||!values)goto failed;
        double load,mu,fx,fy,brake,relative,dx,dy,spin[3],point[3],tangent[3],axle[3],gyro[3],steer[3];
        int supported=PyObject_IsTrue(publish_field(frame,P_SUPPORTED));if(supported<0)goto failed;
        if(!publish_number(frame,P_LOAD,&load)||!publish_number(frame,P_MU,&mu)||!publish_number(step,P_FX,&fx)
            ||!publish_number(step,P_FY,&fy)||!publish_number(step,P_BRAKE_TORQUE,&brake)||!publish_number(step,P_RELATIVE_OMEGA,&relative)
            ||!publish_number(step,P_DEFORMATION_X,&dx)||!publish_number(step,P_DEFORMATION_Y,&dy)
            ||!publish_vector(publish_field(frame,P_POINT),point)||!publish_vector(publish_field(frame,P_TANGENT),tangent)
            ||!publish_vector(publish_field(frame,P_AXLE),axle))goto failed;
        if(rotor){if(!publish_number(frame,P_ROLLING_RADIUS,&radius)||!publish_vector(publish_field(frame,P_SPIN_AXIS),spin)
            ||!publish_vector(publish_field(step,P_GYRO_TORQUE),gyro)||!publish_vector(publish_field(step,P_STEERING_TORQUE),steer))goto failed;}
        else memcpy(spin,axle,sizeof(spin));
        double force[3],moment[3],point_single[3],drive=PyFloat_AsDouble(PyTuple_GET_ITEM(drives,i));
        if(PyErr_Occurred())goto failed;
        /* 只在原Panda Vec3边界转单精度，乘法/加法顺序和原代码一致。 */
        for(int a=0;a<3;++a){float tx=(float)((float)tangent[a]*(float)fx),ty=(float)((float)axle[a]*(float)fy);
            force[a]=(float)((float)(tx+ty)*(float)dt);point_single[a]=(float)point[a];
            moment[a]=(float)((float)spin[a]*(float)(dt*(drive-brake-radius*fx)));}
        if(!publish_impulse(impulses,"point",force,point_single)||!publish_impulse(impulses,"torque",moment,NULL))goto failed;
        if(rotor){for(int a=0;a<3;++a)moment[a]=(float)(dt*(gyro[a]+steer[a]));
            if(!publish_impulse(impulses,"torque",moment,NULL))goto failed;}
        double angle=PyFloat_AsDouble(PyTuple_GET_ITEM(rotation,i));if(PyErr_Occurred())goto failed;angle+=dt*relative;
        PyObject *value=publish_field(step,P_OMEGA);if(!value)goto failed;
        PyTuple_SET_ITEM(omegas,i,Py_NewRef(value));PyTuple_SET_ITEM(angles,i,PyFloat_FromDouble(angle));
        if(!PyTuple_GET_ITEM(angles,i))goto failed;
        if(compliance||rotor){double basis_x[3],basis_y[3],world[3];PyObject *basis=publish_field(frame,P_ELASTIC_FRAME);
            if(!basis||!publish_vector(PyTuple_GET_ITEM(basis,0),basis_x)||!publish_vector(PyTuple_GET_ITEM(basis,1),basis_y))goto failed;
            for(int a=0;a<3;++a)world[a]=dx*basis_x[a]+dy*basis_y[a];
            PyTuple_SET_ITEM(elastic,i,Py_BuildValue("(ddd)",world[0],world[1],world[2]));
        }else PyTuple_SET_ITEM(elastic,i,Py_NewRef(PyTuple_GET_ITEM(deformation,i)));
        if(!PyTuple_GET_ITEM(elastic,i)||!publish_float(values,P_ROTATION,angle))goto failed;
        const int direct[][2]={{P_OMEGA,P_OMEGA},{P_RELATIVE_OMEGA,P_RELATIVE_OMEGA},{P_LONGITUDINAL_SPEED,P_VX},{P_LATERAL_SPEED,P_VY},
            {P_FX,P_FX},{P_FY,P_FY},{P_BRAKE_TORQUE,P_BRAKE_TORQUE},{P_FORCE_RESIDUAL,P_RESIDUAL},{P_FORCE_MODE,P_MODE},
            {P_DEFORMATION_X,P_DEFORMATION_X},{P_DEFORMATION_Y,P_DEFORMATION_Y},{P_ELASTIC_ENERGY,P_ELASTIC_ENERGY},
            {P_DEFORMATION_RATE_X,P_DEFORMATION_RATE_X},{P_DEFORMATION_RATE_Y,P_DEFORMATION_RATE_Y},{P_ROLLING_TORQUE,P_ROLLING_TORQUE}};
        for(int k=0;k<15;++k)if(!publish_copy(values,direct[k][0],step,direct[k][1]))goto failed;
        const int slips[][2]={{P_KAPPA,P_KAPPA},{P_ALPHA,P_ALPHA},{P_FORCE_KAPPA,P_KAPPA},{P_FORCE_ALPHA,P_ALPHA},
            {P_FORCE_PATCH_KAPPA,P_PATCH_KAPPA},{P_FORCE_PATCH_ALPHA,P_PATCH_ALPHA}};
        for(int k=0;k<6;++k)if(!publish_put(values,slips[k][0],supported?publish_field(step,slips[k][1]):Py_None))goto failed;
        if(!publish_put(values,P_DRIVE_TORQUE,PyTuple_GET_ITEM(drives,i))||!publish_put(values,P_BRAKE_CAPACITY,PyTuple_GET_ITEM(capacities,i))
            ||!publish_copy(values,P_NORMAL_LOAD,frame,P_LOAD)||!publish_put(values,P_ROAD_SUPPORT,supported?Py_True:Py_False)
            ||!publish_copy(values,P_STEERING,frame,P_STEERING)||!publish_put(values,P_FORCE_CONTACT_TICK,tick)
            ||!publish_put(values,P_FRAME_DISSIPATION,PyTuple_GET_ITEM(losses,i)))goto failed;
        const int totals[][2]={{P_LONGITUDINAL_IMPULSE,P_FX},{P_LATERAL_IMPULSE,P_FY},{P_BRAKE_ANGULAR_IMPULSE,P_BRAKE_TORQUE},
            {P_ROLLING_ANGULAR_IMPULSE,P_ROLLING_TORQUE},{P_ROLLING_DISSIPATION,P_ROLLING_DISSIPATION},
            {P_MATERIAL_DISSIPATION,P_MATERIAL_DISSIPATION},{P_ROAD_DISSIPATION,P_ROAD_DISSIPATION},
            {P_ELASTIC_NUMERICAL_DISSIPATION,P_ELASTIC_NUMERICAL_DISSIPATION}};
        for(int k=0;k<8;++k){double delta;if(!publish_number(step,totals[k][1],&delta))goto failed;
            if(k<4)delta=dt*delta;
            if(!publish_accumulate(values,totals[k][0],old,totals[k][0],delta,accumulate))goto failed;}
        double nominal=mass*9.81/4,ratio=load/nominal,cx,cy,ex,ey,wheel_mass;PyObject *wheel=i<2?hardware:rear_hardware;
        if(!publish_number(wheel,P_LONGITUDINAL_STIFFNESS,&cx)||!publish_number(wheel,P_LATERAL_STIFFNESS,&cy)
            ||!publish_number(wheel,P_LONGITUDINAL_LOAD_EXPONENT,&ex)||!publish_number(wheel,P_LATERAL_LOAD_EXPONENT,&ey)
            ||!publish_number(wheel,P_MASS,&wheel_mass))goto failed;
        if(!publish_float(values,P_FORCE_GRIP,load==0.?0.:mu*load*pow(ratio,peak-1))
            ||!publish_float(values,P_FORCE_LONGITUDINAL_STIFFNESS,cx*pow(load/(wheel_mass*9.81/4),ex))
            ||!publish_float(values,P_FORCE_LATERAL_STIFFNESS,cy*pow(load/(wheel_mass*9.81/4),ey)))goto failed;
        double axis[3]={0.,0.,0.};if(rotor)memcpy(axis,spin,sizeof(axis));
        if(!publish_three(values,P_MECHANICAL_AXIS,axis)||!publish_put(values,P_ROLLING_RADIUS,rotor?publish_field(frame,P_ROLLING_RADIUS):Py_None)
            ||!publish_put(values,P_FORCE_ROLLING_RADIUS,publish_field(rotor?frame:hardware,rotor?P_ROLLING_RADIUS:P_WHEEL_RADIUS)))goto failed;
        if(rotor){double mx[3],my[3],products[3];publish_cross(point,tangent,mx);publish_cross(point,axle,my);
            const int vector_keys[]={P_GYRO_ANGULAR_IMPULSE,P_STEERING_ANGULAR_IMPULSE,P_LONGITUDINAL_ANGULAR_IMPULSE,P_LATERAL_ANGULAR_IMPULSE};
            for(int k=0;k<4;++k){double out[3]={0.,0.,0.};if(accumulate&&!publish_vector(publish_field(old,vector_keys[k]),out))goto failed;
                for(int a=0;a<3;++a)out[a]+=k==0?dt*gyro[a]:k==1?dt*steer[a]:k==2?dt*fx*mx[a]:dt*fy*my[a];
                if(!publish_three(values,vector_keys[k],out))goto failed;}
            for(int a=0;a<3;++a)products[a]=end_angular[a]*steer[a];
            if(!publish_accumulate(values,P_STEERING_WORK,old,P_STEERING_WORK,dt*sum_three(products),accumulate))goto failed;
        }else if(accumulate){const int saved[]={P_GYRO_ANGULAR_IMPULSE,P_STEERING_ANGULAR_IMPULSE,P_LONGITUDINAL_ANGULAR_IMPULSE,P_LATERAL_ANGULAR_IMPULSE,P_STEERING_WORK};
            for(int k=0;k<5;++k)if(!publish_copy(values,saved[k],old,saved[k]))goto failed;}
        PyObject *state=PyType_GenericAlloc(Py_TYPE(empty),0);if(!state)goto failed;
        if(PyObject_GenericSetDict(state,values,NULL)){Py_DECREF(state);goto failed;}PyTuple_SET_ITEM(states,i,state);
        Py_CLEAR(frame);Py_CLEAR(step);Py_CLEAR(old);Py_CLEAR(values);
    }
    PyObject *ordered=PyList_AsTuple(impulses);if(!ordered)goto failed;
    Py_DECREF(hardware);Py_DECREF(rear_hardware);Py_DECREF(defaults);Py_DECREF(impulses);
    return Py_BuildValue("NNNNN",omegas,angles,elastic,states,ordered);
failed:
    Py_XDECREF(hardware);Py_XDECREF(rear_hardware);Py_XDECREF(defaults);Py_XDECREF(states);Py_XDECREF(angles);
    Py_XDECREF(omegas);Py_XDECREF(elastic);Py_XDECREF(impulses);Py_XDECREF(frame);Py_XDECREF(step);Py_XDECREF(old);Py_XDECREF(values);return NULL;
}
