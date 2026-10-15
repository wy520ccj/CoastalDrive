#ifndef COASTAL_LAB_CONTACT_NATIVE_H
#define COASTAL_LAB_CONTACT_NATIVE_H

/* 仅供独立轮心试验台：读取真实查询后的四轮数组，不拥有世界或积分状态。 */
static int lab_array(PyObject *object,Py_buffer *view,int dimensions,const Py_ssize_t *shape,int writable) {
    if (PyObject_GetBuffer(object,view,PyBUF_STRIDES|PyBUF_FORMAT|(writable ? PyBUF_WRITABLE : 0))<0) return 0;
    if (view->ndim!=dimensions || view->itemsize!=sizeof(double) || strcmp(view->format,"d")) {
        PyErr_SetString(PyExc_ValueError,"试验台原生数组须为指定维数的本机双精度浮点"); return 0;
    }
    for (int i=0;i<dimensions;++i) if (view->shape[i]!=shape[i]) {
        PyErr_SetString(PyExc_ValueError,"试验台原生数组形状不符"); return 0;
    }
    return 1;
}
static double lab_get(const Py_buffer *view,int i,int j) {
    double value;
    memcpy(&value,(char *)view->buf+i*view->strides[0]+(view->ndim==1 ? 0 : j*view->strides[1]),sizeof(value));
    return value;
}
static void lab_set(const Py_buffer *view,int i,int j,double value) {
    memcpy((char *)view->buf+i*view->strides[0]+(view->ndim==1 ? 0 : j*view->strides[1]),&value,sizeof(value));
}
static void lab_row(const Py_buffer *view,int i,double value[3]) {
    for (int j=0;j<3;++j) value[j]=lab_get(view,i,j);
}
/* 保留NumPy三元素dot的原顺序；这里不能改用补偿dot或融合乘加。 */
static double lab_dot(const double a[3],const double b[3]) {
    double result=0.;
    for (int i=0;i<3;++i) result+=a[i]*b[i];
    return result;
}
static int lab_buffers(PyObject *inputs,PyObject *outputs,Py_buffer *views,int input_count,int output_count,
                       const int *dimensions,const Py_ssize_t shapes[][3],int optional_first,int optional_last) {
    if (!PyTuple_Check(inputs) || PyTuple_GET_SIZE(inputs)!=input_count || !PyTuple_Check(outputs)
        || PyTuple_GET_SIZE(outputs)!=output_count) {
        PyErr_SetString(PyExc_ValueError,"试验台原生输入/输出数组数量不符"); return 0;
    }
    for (int i=0;i<input_count+output_count;++i) {
        PyObject *object=PyTuple_GET_ITEM(i<input_count ? inputs : outputs,i<input_count ? i : i-input_count);
        if (i>=optional_first && i<=optional_last && object==Py_None) continue;
        if (!lab_array(object,&views[i],dimensions[i],shapes[i],i>=input_count)) return 0;
    }
    return 1;
}
static void lab_release(Py_buffer *views,int count) {
    for (int i=0;i<count;++i) if (views[i].obj) PyBuffer_Release(&views[i]);
}

static PyObject *unsprung_tire_ports_native(PyObject *self,PyObject *args) {
    PyObject *inputs,*outputs;
    if (!PyArg_ParseTuple(args,"OO",&inputs,&outputs)) return NULL;
    const int dimensions[15]={2,2,2,2,2,2,2,2,2,1,2,2,3,2,2};
    const Py_ssize_t shapes[15][3]={{4,3},{4,3},{4,3},{4,16},{4,3},{4,3},{4,3},{4,3},{4,3},{4},
                                   {4,3},{4,3},{4,3,16},{4,3},{4,3}};
    Py_buffer v[15]={{0}};
    if (!lab_buffers(inputs,outputs,v,12,3,dimensions,shapes,10,11)) goto error;
    for (int i=0;i<4;++i) {
        double arm[3],guide[3],spin[3],offset[3],steer[3],tangent[3],brake[16];
        lab_row(v,i,arm); lab_row(v+1,i,guide); lab_row(v+4,i,offset);
        lab_row(v+8,i,steer); lab_row(v+5,i,tangent);
        lab_row(v[11].obj ? v+11 : v+2,i,spin);
        for (int j=0;j<16;++j) brake[j]=lab_get(v+3,i,j);
        if (v[11].obj) for (int j=0;j<3;++j) brake[j+3]=spin[j];
        double trail=lab_get(v+9,i,0);
        for (int direction=0;direction<3;++direction) {
            double axis[3],point_offset[3],point[3],gradient[16]={0.},moment[3],radial[3],steer_motion[3];
            lab_row(v+5+direction,i,axis);
            int envelope=direction==2 && v[10].obj;
            for (int j=0;j<3;++j) {
                point_offset[j]=direction==1 ? offset[j]-trail*tangent[j] : offset[j];
                if (envelope) point_offset[j]=lab_get(v+10,i,j);
                point[j]=arm[j]+point_offset[j];
            }
            cross_regular(point,axis,moment);
            for (int j=0;j<3;++j) { gradient[j]=axis[j]; gradient[j+3]=moment[j]; }
            gradient[6+i]=lab_dot(guide,axis);
            cross_regular(point_offset,axis,radial);
            double radius=lab_dot(spin,radial);
            if (envelope) radius=0.;
            else for (int j=0;j<16;++j) gradient[j]-=radius*brake[j];
            cross_regular(steer,point_offset,steer_motion);
            lab_set(v+13,i,direction,radius);
            lab_set(v+14,i,direction,lab_dot(steer_motion,axis));
            for (int j=0;j<16;++j)
                memcpy((char *)v[12].buf+i*v[12].strides[0]+direction*v[12].strides[1]+j*v[12].strides[2],
                       &gradient[j],sizeof(double));
        }
    }
    lab_release(v,15); Py_RETURN_NONE;
error:
    lab_release(v,15); return NULL;
}

static PyObject *finite_radial_gradients_native(PyObject *self,PyObject *args) {
    PyObject *inputs,*outputs;
    double h,radius,half_width,shoulder,crown;
    if (!PyArg_ParseTuple(args,"OOddddd",&inputs,&outputs,&h,&radius,&half_width,&shoulder,&crown)) return NULL;
    const int dimensions[18]={2,2,2,2,2,1,2,2,1,1,2,1,1,2,1,2,2,2};
    const Py_ssize_t shapes[18][3]={{4,3},{4,3},{4,3},{4,3},{4,3},{3},{4,3},{4,3},{4},{4},
                                  {4,3},{4},{4},{4,16},{4},{4,3},{4,3},{4,3}};
    Py_buffer v[18]={{0}};
    if (!lab_buffers(inputs,outputs,v,13,5,dimensions,shapes,-1,-1)) goto error;
    double angular[3];
    for (int j=0;j<3;++j) angular[j]=lab_get(v+5,j,0);
    for (int i=0;i<4;++i) {
        double normal[3],axis[3],negative[3],support_point[3],meridian[3],temp[3],wheel[3],surface[3];
        lab_row(v,i,normal); lab_row(v+1,i,axis); lab_row(v+4,i,wheel);
        for (int j=0;j<3;++j) negative[j]=-normal[j];
        if (!support_values(negative,axis,radius,half_width,shoulder,crown,support_point)) goto error;
        cross_regular(axis,normal,meridian);
        double squared=lab_dot(meridian,meridian);
        cross_regular(support_point,normal,temp);
        double lever=squared!=0. ? lab_dot(temp,meridian)/squared : 0.;
        for (int j=0;j<3;++j) temp[j]=lever*axis[j];
        cross_regular(angular,temp,surface);
        for (int j=0;j<3;++j) surface[j]=wheel[j]+surface[j];
        double motion=lab_dot(surface,surface);
        if (lab_get(v+12,i,0)!=0. && motion>0.) {
            double delta=lab_get(v+9,i,0)-lab_get(v+8,i,0);
            if (lab_get(v+11,i,0)!=0.) {
                double plane[3],old_axis[3],average[3];
                lab_row(v+10,i,plane); lab_row(v+2,i,old_axis); lab_row(v+3,i,average);
                double eta=lab_dot(plane,old_axis);
                cross_regular(angular,average,temp);
                double change=h*lab_dot(plane,temp);
                double extent=crown_secant_value(eta,eta+change,radius,half_width,shoulder,crown);
                delta=extent*change-h*lab_dot(plane,wheel);
            }
            double desired=-delta/h,factor=desired-lab_dot(normal,surface);
            for (int j=0;j<3;++j) normal[j]=normal[j]+factor*surface[j]/motion;
        }
        double scale=sqrt(lab_dot(normal,normal));
        if (scale==0.) { PyErr_SetString(PyExc_ArithmeticError,"有限径向接触的空间梯度退化"); goto error; }
        lab_set(v+14,i,0,scale);
        double arm[3],guide[3],tangent[3],lateral[3];
        lab_row(v+6,i,arm); lab_row(v+7,i,guide);
        for (int j=0;j<3;++j) {
            normal[j]/=scale;
            temp[j]=arm[j]+lever*axis[j];
            lab_set(v+15,i,j,normal[j]);
        }
        cross_regular(temp,normal,meridian);
        for (int j=0;j<16;++j) lab_set(v+13,i,j,0.);
        for (int j=0;j<3;++j) { lab_set(v+13,i,j,normal[j]); lab_set(v+13,i,j+3,meridian[j]); }
        lab_set(v+13,i,6+i,lab_dot(guide,normal));
        cross_regular(normal,axis,tangent);
        double tangent_length=sqrt(lab_dot(tangent,tangent));
        for (int j=0;j<3;++j) { tangent[j]/=tangent_length; lab_set(v+16,i,j,tangent[j]); }
        cross_regular(tangent,normal,lateral);
        for (int j=0;j<3;++j) lab_set(v+17,i,j,lateral[j]);
    }
    lab_release(v,18); Py_RETURN_NONE;
error:
    lab_release(v,18); return NULL;
}
/* 车身陀螺残差仍使用原生轮心实际力；这里只按原四轮顺序归集力矩。 */
static PyObject *unsprung_body_torque_native(PyObject *self,PyObject *args) {
    PyObject *inputs,*outputs;
    if (!PyArg_ParseTuple(args,"OO",&inputs,&outputs)) return NULL;
    const int dimensions[5]={2,2,1,1,1};
    const Py_ssize_t shapes[5][3]={{4,3},{4,3},{16},{16},{3}};
    Py_buffer v[5]={{0}};
    if (!lab_buffers(inputs,outputs,v,4,1,dimensions,shapes,-1,-1)) goto error;
    double total[3]={0.};
    for (int i=0;i<4;++i) {
        double arm[3],force[3],moment[3];
        lab_row(v,i,arm); lab_row(v+1,i,force);
        cross_regular(arm,force,moment);
        for (int j=0;j<3;++j) total[j]+=moment[j];
    }
    for (int j=0;j<3;++j) lab_set(v+4,j,0,lab_get(v+2,j+3,0)-lab_get(v+3,j+3,0)-total[j]);
    lab_release(v,5); Py_RETURN_NONE;
error:
    lab_release(v,5); return NULL;
}
#include <limits.h>

/* 矩阵变换留在原NumPy路径；批量执行相同局部平面支持距离与见证点公式。 */
static PyObject *radial_plane_values_native(PyObject *self,PyObject *args) {
    PyObject *inputs,*outputs;
    Py_ssize_t count;
    double radius,half_width,shoulder,crown,constant;
    if (!PyArg_ParseTuple(args,"OOnddddd",&inputs,&outputs,&count,&radius,&half_width,&shoulder,&crown,&constant)) return NULL;
    if (count<0 || count>INT_MAX) { PyErr_SetString(PyExc_ValueError,"径向查询批量尺寸超出本机索引范围"); return NULL; }
    const int dimensions[6]={2,2,1,1,1,2};
    const Py_ssize_t shapes[6][3]={{count,3},{count,3},{3},{3},{count},{count,3}};
    Py_buffer v[6]={{0}};
    if (!lab_buffers(inputs,outputs,v,4,2,dimensions,shapes,-1,-1)) goto error;
    double normal[3],negative[3],translation[3];
    for (int j=0;j<3;++j) { normal[j]=lab_get(v+2,j,0); negative[j]=-normal[j]; translation[j]=lab_get(v+3,j,0); }
    for (int i=0;i<(int)count;++i) {
        double center[3],axis[3],lower[3],wheel[3];
        lab_row(v,i,center); lab_row(v+1,i,axis);
        if (!support_values(negative,axis,radius,half_width,shoulder,crown,lower)) goto error;
        for (int j=0;j<3;++j) wheel[j]=center[j]+lower[j];
        double distance=lab_dot(normal,wheel)-constant;
        lab_set(v+4,i,0,distance);
        for (int j=0;j<3;++j) lab_set(v+5,i,j,(wheel[j]-distance*normal[j])-translation[j]);
    }
    lab_release(v,6); Py_RETURN_NONE;
error:
    lab_release(v,6); return NULL;
}

/* 保留原已选接触/腾空分支及算术顺序；不参与候选裁剪或支撑资格选择。 */
static PyObject *radial_contact_frames_native(PyObject *self,PyObject *args) {
    PyObject *inputs,*outputs;
    Py_ssize_t count;
    double radius,half_width,shoulder,crown,travel;
    if (!PyArg_ParseTuple(args,"OOnddddd",&inputs,&outputs,&count,&radius,&half_width,&shoulder,&crown,&travel)) return NULL;
    if (count<0 || count>INT_MAX) { PyErr_SetString(PyExc_ValueError,"径向查询批量尺寸超出本机索引范围"); return NULL; }
    const int dimensions[13]={2,2,1,1,1,2,2,1,2,2,2,2,2};
    const Py_ssize_t shapes[13][3]={{count,3},{count,3},{3},{count},{count},{count,3},{count,3},
                                  {count},{count,3},{count,3},{count,3},{count,3},{count,3}};
    Py_buffer v[13]={{0}};
    if (!lab_buffers(inputs,outputs,v,7,6,dimensions,shapes,-1,-1)) goto error;
    for (int i=0;i<(int)count;++i) {
        double center[3],axis[3],normal[3],offset[3],negative[3],support_point[3],tangent[3],lateral[3];
        lab_row(v,i,center); lab_row(v+1,i,axis);
        double compression;
        if (lab_get(v+3,i,0)==0.) {
            compression=-radius-travel;
            for (int j=0;j<3;++j) { normal[j]=lab_get(v+2,j,0); offset[j]=-radius*normal[j]; }
        } else {
            compression=-lab_get(v+4,i,0);
            lab_row(v+6,i,normal);
            for (int j=0;j<3;++j) offset[j]=lab_get(v+5,i,j)-center[j];
        }
        cross_regular(normal,axis,tangent);
        double length=sqrt(lab_dot(tangent,tangent));
        for (int j=0;j<3;++j) { tangent[j]/=length; negative[j]=-normal[j]; }
        if (!support_values(negative,axis,radius,half_width,shoulder,crown,support_point)) goto error;
        cross_regular(tangent,normal,lateral);
        lab_set(v+7,i,0,compression);
        for (int j=0;j<3;++j) {
            lab_set(v+8,i,j,offset[j]); lab_set(v+9,i,j,normal[j]);
            lab_set(v+10,i,j,tangent[j]); lab_set(v+11,i,j,lateral[j]);
            lab_set(v+12,i,j,support_point[j]+compression*normal[j]);
        }
    }
    lab_release(v,13); Py_RETURN_NONE;
error:
    lab_release(v,13); return NULL;
}
#endif
