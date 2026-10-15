#ifndef COASTAL_LAB_JOINT_NATIVE_H
#define COASTAL_LAB_JOINT_NATIVE_H

/* 仅试验台固定维数残差；原材料函数及math.hypot仍是唯一计算入口。 */
static double lab_joint_get(const Py_buffer *view,int i,int j) {
    double value;
    memcpy(&value,(char *)view->buf+i*view->strides[0]+(view->ndim==1 ? 0 : j*view->strides[1]),sizeof(value));
    return value;
}
static void lab_joint_set(const Py_buffer *view,int i,double value) {
    memcpy((char *)view->buf+i*view->strides[0],&value,sizeof(value));
}
static int lab_joint_buffers(PyObject *inputs,PyObject *output,Py_buffer *views,int count,
                             const int *dimensions,const Py_ssize_t shapes[][2]) {
    if (!PyTuple_Check(inputs) || PyTuple_GET_SIZE(inputs)!=count) {
        PyErr_SetString(PyExc_ValueError,"试验台残差输入数组数量不符"); return 0;
    }
    for (int i=0;i<=count;++i) {
        PyObject *object=i==count ? output : PyTuple_GET_ITEM(inputs,i);
        if (PyObject_GetBuffer(object,views+i,PyBUF_STRIDES|PyBUF_FORMAT|(i==count ? PyBUF_WRITABLE : 0))<0) return 0;
        if (views[i].ndim!=dimensions[i] || views[i].itemsize!=sizeof(double) || strcmp(views[i].format,"d")) {
            PyErr_SetString(PyExc_ValueError,"试验台残差数组须为指定维数的本机双精度浮点"); return 0;
        }
        for (int j=0;j<dimensions[i];++j) if (views[i].shape[j]!=shapes[i][j]) {
            PyErr_SetString(PyExc_ValueError,"试验台残差数组形状不符"); return 0;
        }
    }
    return 1;
}
static void lab_joint_release(Py_buffer *views,int count) {
    for (int i=0;i<count;++i) if (views[i].obj) PyBuffer_Release(views+i);
}

static PyObject *unsprung_contact_residual_native(PyObject *self,PyObject *args) {
    PyObject *inputs,*output,*hypot_function,*details=NULL;
    double dt,stiffness,damping,shape,curvature,slip_speed;
    if (!PyArg_ParseTuple(args,"OOddddddO",&inputs,&output,&dt,&stiffness,&damping,&shape,&curvature,&slip_speed,&hypot_function)) return NULL;
    const int dimensions[8]={1,2,2,2,1,1,2,1};
    const Py_ssize_t shapes[8][2]={{16},{4,2},{4,2},{4,3},{4},{4},{4,3},{34}};
    Py_buffer v[8]={{0}};
    if (!lab_joint_buffers(inputs,output,v,7,dimensions,shapes)) goto error;
    details=PyList_New(4); if (!details) goto error;
    for (int i=0;i<4;++i) {
        double force[2],previous[2],slip[2],target[2],deformation[2],rate[2],patch[2],kappa,alpha;
        const char *mode;
        for (int j=0;j<2;++j) {
            force[j]=lab_joint_get(v+1,i,j); previous[j]=lab_joint_get(v+2,i,j); slip[j]=-lab_joint_get(v+3,i,j);
        }
        double vx=lab_joint_get(v+3,i,0)+lab_joint_get(v+4,i,0)*lab_joint_get(v,12+i,0);
        double denominator=fabs(vx); if (slip_speed>denominator) denominator=slip_speed;
        if (!tire_contact_values(force,previous,slip,denominator,lab_joint_get(v+5,i,0)!=0.,
            lab_joint_get(v+6,i,0),lab_joint_get(v+6,i,1),lab_joint_get(v+6,i,2),dt,stiffness,damping,
            shape,curvature,hypot_function,target,deformation,rate,patch,&kappa,&alpha,&mode)) goto error;
        PyObject *value=Py_BuildValue("((dd)(dd)(dd)(dd)dds)",target[0],target[1],deformation[0],deformation[1],
            rate[0],rate[1],patch[0],patch[1],kappa,alpha,mode);
        if (!value) goto error;
        PyList_SET_ITEM(details,i,value);
        for (int j=0;j<2;++j) lab_joint_set(v+7,16+2*i+j,force[j]-target[j]);
    }
    lab_joint_release(v,8); return details;
error:
    Py_XDECREF(details); lab_joint_release(v,8); return NULL;
}

/* 原标量clip相等时保留输入；数组clip则先max下界、再min上界，零符号不同。 */
static double lab_joint_clip(double value,double lower,double upper) {
    if (lower>upper) return upper;
    if (value<lower) return lower;
    if (value>upper) return upper;
    return value;
}
static double lab_joint_array_clip(double value,double lower,double upper) {
    if (isnan(value)) return value;
    if (isnan(lower)) return lower;
    if (isnan(upper)) return upper;
    value=value>lower ? value : lower;
    return value<upper ? value : upper;
}
static PyObject *unsprung_port_residual_native(PyObject *self,PyObject *args) {
    PyObject *inputs,*output,*settings;
    double drive,dt,ratio,share,final_drive,efficiency,clutch,sync_capacity;
    int synchronizing;
    if (!PyArg_ParseTuple(args,"OOOd",&inputs,&output,&settings,&drive)) return NULL;
    if (!PyArg_ParseTuple(settings,"ddpddddd",&dt,&ratio,&synchronizing,&share,&final_drive,&efficiency,&clutch,&sync_capacity)) return NULL;
    const int dimensions[9]={1,1,1,1,1,1,1,1,1};
    const Py_ssize_t shapes[9][2]={{10},{10},{10},{3},{4},{3},{2},{3},{34}};
    Py_buffer v[9]={{0}};
    if (!lab_joint_buffers(inputs,output,v,8,dimensions,shapes)) goto error;
    double torque[10],speed[10],response[10],limits[3],axle[2];
    for (int i=0;i<10;++i) { torque[i]=lab_joint_get(v,i,0); speed[i]=lab_joint_get(v+1,i,0); response[i]=lab_joint_get(v+2,i,0); }
    axle[0]=share*drive-final_drive*(share*lab_joint_get(v+3,0,0)+lab_joint_get(v+3,1,0));
    axle[1]=(1-share)*drive-final_drive*((1-share)*lab_joint_get(v+3,0,0)+lab_joint_get(v+3,2,0));
    for (int i=0;i<3;++i) {
        limits[i]=lab_joint_get(v+5,i,0);
        if (i<2) {
            double bias=lab_joint_get(v+6,i,0);
            if (bias>1.) {
                double capacity=fabs(axle[i])*(bias-1.)/(2*(bias+1.));
                if (capacity<limits[i]) limits[i]=capacity;
            }
        }
    }
    double error_g,error_l;
    if (ratio!=0. && !synchronizing) {
        error_g=speed[1]/(dt*response[1]);
        double slope=torque[1]*speed[2]>=0. ? 1-efficiency : 1-1/efficiency;
        error_l=torque[2]-slope*torque[1];
    } else if (ratio!=0.) {
        error_g=torque[1]-lab_joint_clip(torque[1]+speed[1]/(dt*response[1]),-sync_capacity,sync_capacity);
        error_l=torque[2];
    } else { error_g=torque[1]; error_l=torque[2]; }
    lab_joint_set(v+8,24,torque[0]-lab_joint_clip(torque[0]+speed[0]/(dt*response[0]),-clutch,clutch));
    lab_joint_set(v+8,25,error_g); lab_joint_set(v+8,26,error_l);
    for (int i=0;i<4;++i) {
        double capacity=lab_joint_get(v+4,i,0);
        lab_joint_set(v+8,27+i,torque[3+i]-lab_joint_array_clip(torque[3+i]+speed[3+i]/(dt*response[3+i]),-capacity,capacity));
    }
    for (int i=0;i<3;++i) lab_joint_set(v+8,31+i,torque[7+i]-lab_joint_array_clip(lab_joint_get(v+7,i,0)*speed[7+i],-limits[i],limits[i]));
    lab_joint_release(v,9); Py_RETURN_NONE;
error:
    lab_joint_release(v,9); return NULL;
}
#endif
