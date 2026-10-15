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
typedef struct {
    double center[3],axis[3],basis[2][3],edge[3];
    double radius,half_width,shoulder,crown;
    PyObject *cosine,*sine;
} LabBoxCone;

/* 保留原NumPy标量sin/cos与三元素dot顺序；只消除临时小向量和重复包装。 */
static int lab_box_evaluate(const LabBoxCone *cone,double angle,double normal[3],double wheel[3],double values[2]) {
    PyObject *result=PyObject_CallFunction(cone->cosine,"d",angle);
    if (!result) return 0;
    double cosine=PyFloat_AsDouble(result); Py_DECREF(result); if (PyErr_Occurred()) return 0;
    result=PyObject_CallFunction(cone->sine,"d",angle);
    if (!result) return 0;
    double sine=PyFloat_AsDouble(result); Py_DECREF(result); if (PyErr_Occurred()) return 0;
    double tangent[3],negative[3],support_point[3],delta[3];
    for (int j=0;j<3;++j) {
        normal[j]=cosine*cone->basis[0][j]+sine*cone->basis[1][j];
        tangent[j]=-sine*cone->basis[0][j]+cosine*cone->basis[1][j];
        negative[j]=-normal[j];
    }
    if (!support_values(negative,cone->axis,cone->radius,cone->half_width,cone->shoulder,cone->crown,support_point)) return 0;
    for (int j=0;j<3;++j) { wheel[j]=cone->center[j]+support_point[j]; delta[j]=wheel[j]-cone->edge[j]; }
    values[0]=lab_dot(normal,delta); values[1]=lab_dot(tangent,delta);
    return 1;
}
static void lab_box_store(Py_buffer *views,int row,const double normal[3],const double wheel[3],const double values[2]) {
    for (int j=0;j<3;++j) { lab_set(views+4,row,j,normal[j]); lab_set(views+5,row,j,wheel[j]); }
    for (int j=0;j<2;++j) lab_set(views+6,row,j,values[j]);
}
static PyObject *lab_box_cone_call(PyObject *args,int refine) {
    PyObject *inputs,*outputs;
    LabBoxCone cone;
    double ceiling;
    if (!PyArg_ParseTuple(args,"OOdddddOO",&inputs,&outputs,&cone.radius,&cone.half_width,&cone.shoulder,&cone.crown,
        &ceiling,&cone.cosine,&cone.sine)) return NULL;
    const int dimensions[7]={1,1,2,1,2,2,2};
    const Py_ssize_t shapes[7][3]={{3},{3},{2,3},{3},{3,3},{3,3},{3,2}};
    Py_buffer v[7]={{0}};
    if (!lab_buffers(inputs,outputs,v,4,3,dimensions,shapes,-1,-1)) goto error;
    for (int j=0;j<3;++j) { cone.center[j]=lab_get(v,j,0); cone.axis[j]=lab_get(v+1,j,0); cone.edge[j]=lab_get(v+3,j,0); }
    for (int j=0;j<2;++j) lab_row(v+2,j,cone.basis[j]);
    double normal[3],wheel[3],values[2];
    if (!refine) {
        for (int row=0;row<2;++row) {
            if (!lab_box_evaluate(&cone,row==0 ? 0. : ceiling,normal,wheel,values)) goto error;
            lab_box_store(v,row,normal,wheel,values);
        }
    } else {
        double lo=0.,hi=ceiling;
        for (int iteration=0;iteration<52;++iteration) {
            double middle=(lo+hi)/2;
            if (!lab_box_evaluate(&cone,middle,normal,wheel,values)) goto error;
            if (values[1]>0.) lo=middle; else hi=middle;
        }
        if (!lab_box_evaluate(&cone,(lo+hi)/2,normal,wheel,values)) goto error;
        lab_box_store(v,2,normal,wheel,values);
    }
    lab_release(v,7); Py_RETURN_NONE;
error:
    lab_release(v,7); return NULL;
}
static PyObject *box_cone_samples_native(PyObject *self,PyObject *args) {
    return lab_box_cone_call(args,0);
}
static PyObject *box_cone_refine_native(PyObject *self,PyObject *args) {
    return lab_box_cone_call(args,1);
}
/* 六个轴向仍逐个调用原支持函数；负法线在前，保留零符号及每次支持运算的算术顺序。 */
static int lab_box_axis_values(const double center[3],double axis[3],double radius,double half_width,double shoulder,
                               double crown,double normals[6][3],double wheels[6][3]) {
    for (int index=0;index<3;++index) for (int side=0;side<2;++side) {
        int row=2*index+side;
        double sign=side==0 ? -1. : 1.,direction[3],support_point[3];
        for (int j=0;j<3;++j) { normals[row][j]=sign*(j==index ? 1. : 0.); direction[j]=-normals[row][j]; }
        if (!support_values(direction,axis,radius,half_width,shoulder,crown,support_point)) return 0;
        for (int j=0;j<3;++j) wheels[row][j]=center[j]+support_point[j];
    }
    return 1;
}
static PyObject *box_axis_supports_native(PyObject *self,PyObject *args) {
    PyObject *inputs,*outputs;
    double radius,half_width,shoulder,crown;
    if (!PyArg_ParseTuple(args,"OOdddd",&inputs,&outputs,&radius,&half_width,&shoulder,&crown)) return NULL;
    const int dimensions[4]={1,1,2,2};
    const Py_ssize_t shapes[4][3]={{3},{3},{6,3},{6,3}};
    Py_buffer v[4]={{0}};
    if (!lab_buffers(inputs,outputs,v,2,2,dimensions,shapes,-1,-1)) goto error;
    double center[3],axis[3],normals[6][3],wheels[6][3];
    for (int j=0;j<3;++j) { center[j]=lab_get(v,j,0); axis[j]=lab_get(v+1,j,0); }
    if (!lab_box_axis_values(center,axis,radius,half_width,shoulder,crown,normals,wheels)) goto error;
    for (int i=0;i<6;++i) for (int j=0;j<3;++j) {
        lab_set(v+2,i,j,normals[i][j]); lab_set(v+3,i,j,wheels[i][j]);
    }
    lab_release(v,4); Py_RETURN_NONE;
error:
    lab_release(v,4); return NULL;
}
static double lab_box_maximum(double first,double second) {
    if (isnan(first)) return first;
    if (isnan(second)) return second;
    return first>second ? first : second;
}
static PyObject *radial_box_bounds_native(PyObject *self,PyObject *args) {
    PyObject *inputs,*outputs;
    double radius,half_width,shoulder,crown;
    if (!PyArg_ParseTuple(args,"OOdddd",&inputs,&outputs,&radius,&half_width,&shoulder,&crown)) return NULL;
    const int dimensions[4]={1,1,1,1};
    const Py_ssize_t shapes[4][3]={{3},{3},{3},{3}};
    Py_buffer v[4]={{0}};
    if (!lab_buffers(inputs,outputs,v,3,1,dimensions,shapes,-1,-1)) goto error;
    double center[3],axis[3],normals[6][3],wheels[6][3];
    for (int j=0;j<3;++j) { center[j]=lab_get(v,j,0); axis[j]=lab_get(v+1,j,0); }
    if (!lab_box_axis_values(center,axis,radius,half_width,shoulder,crown,normals,wheels)) goto error;
    for (int j=0;j<3;++j) {
        double half=lab_get(v+2,j,0),minimum=wheels[2*j+1][j],maximum=wheels[2*j][j];
        lab_set(v+3,j,0,lab_box_maximum(lab_box_maximum(minimum-half,-half-maximum),0.));
    }
    lab_release(v,4); Py_RETURN_NONE;
error:
    lab_release(v,4); return NULL;
}
/* 面候选保持原dot、投影和资格判定；仍由Python按原轴序选择全局证明分支。 */
static PyObject *box_face_candidates_native(PyObject *self,PyObject *args) {
    PyObject *inputs,*outputs;
    double radius,half_width,shoulder,crown,tolerance;
    if (!PyArg_ParseTuple(args,"OOddddd",&inputs,&outputs,&radius,&half_width,&shoulder,&crown,&tolerance)) return NULL;
    const int dimensions[8]={1,1,1,2,2,1,2,1};
    const Py_ssize_t shapes[8][3]={{3},{3},{3},{6,3},{6,3},{6},{6,3},{6}};
    Py_buffer v[8]={{0}};
    if (!lab_buffers(inputs,outputs,v,3,5,dimensions,shapes,-1,-1)) goto error;
    double center[3],axis[3],half[3],normals[6][3],wheels[6][3];
    for (int j=0;j<3;++j) { center[j]=lab_get(v,j,0); axis[j]=lab_get(v+1,j,0); half[j]=lab_get(v+2,j,0); }
    if (!lab_box_axis_values(center,axis,radius,half_width,shoulder,crown,normals,wheels)) goto error;
    for (int row=0;row<6;++row) {
        double distance=lab_dot(normals[row],wheels[row])-half[row/2];
        int eligible=1;
        for (int j=0;j<3;++j) {
            double road=wheels[row][j]-distance*normals[row][j];
            lab_set(v+3,row,j,normals[row][j]); lab_set(v+4,row,j,wheels[row][j]); lab_set(v+6,row,j,road);
            if (j!=row/2 && !(fabs(road)<=half[j]+tolerance)) eligible=0;
        }
        lab_set(v+5,row,0,distance); lab_set(v+7,row,0,(double)eligible);
    }
    lab_release(v,8); Py_RETURN_NONE;
error:
    lab_release(v,8); return NULL;
}
/* 四条棱按--、-+、+-、++准备；范数与界限仍沿用原NumPy计算。 */
static PyObject *box_edge_frames_native(PyObject *self,PyObject *args) {
    PyObject *inputs,*outputs;
    int free_axis;
    if (!PyArg_ParseTuple(args,"OOi",&inputs,&outputs,&free_axis)) return NULL;
    if (free_axis<0 || free_axis>2) { PyErr_SetString(PyExc_ValueError,"Box自由轴须为0至2"); return NULL; }
    const int dimensions[5]={1,1,2,2,2};
    const Py_ssize_t shapes[5][3]={{3},{3},{8,3},{4,3},{4,2}};
    Py_buffer v[5]={{0}};
    if (!lab_buffers(inputs,outputs,v,2,3,dimensions,shapes,-1,-1)) goto error;
    int fixed[2],count=0;
    for (int j=0;j<3;++j) if (j!=free_axis) fixed[count++]=j;
    for (int row=0;row<4;++row) {
        for (int j=0;j<3;++j) lab_set(v+3,row,j,0.);
        for (int k=0;k<2;++k) {
            double sign=(row & (k==0 ? 2 : 1)) ? 1. : -1.;
            int index=fixed[k];
            double edge=sign*lab_get(v+1,index,0);
            lab_set(v+3,row,index,edge);
            lab_set(v+4,row,k,(lab_get(v,index,0)-edge)*sign);
            for (int j=0;j<3;++j) lab_set(v+2,2*row+k,j,sign*(j==index ? 1. : 0.));
        }
    }
    lab_release(v,5); Py_RETURN_NONE;
error:
    lab_release(v,5); return NULL;
}
#endif
