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
/* 缓存只保存轴/四个形状参数的完整字节和原支持偏移；无中心、世界或节点。 */
typedef struct {
    int valid;
    double key[7],offsets[6][3];
} LabBoxAxisEntry;
typedef struct {
    LabBoxAxisEntry entries[512];
    unsigned long long hits,misses;
} LabBoxAxisCache;

static PyObject *box_axis_cache_info_native(PyObject *self,PyObject *args) {
    int clear=0;
    if (!PyArg_ParseTuple(args,"|p",&clear)) return NULL;
    LabBoxAxisCache *cache=PyModule_GetState(self);
    if (clear) memset(cache,0,sizeof(*cache));
    return Py_BuildValue("{sK,sK,si}","hits",cache->hits,"misses",cache->misses,"capacity",512);
}

/* 直接映射512槽；哈希冲突只会重算，复用前必须memcmp全部56字节，区分符号零。 */
static int lab_box_axis_values(PyObject *self,const double center[3],double axis[3],double radius,double half_width,double shoulder,
                               double crown,double normals[6][3],double wheels[6][3]) {
    LabBoxAxisCache *cache=PyModule_GetState(self);
    double key[7]={axis[0],axis[1],axis[2],radius,half_width,shoulder,crown};
    const unsigned char *bytes=(const unsigned char *)key;
    unsigned long long hash=14695981039346656037ULL;
    for (size_t i=0;i<sizeof(key);++i) { hash^=bytes[i]; hash*=1099511628211ULL; }
    LabBoxAxisEntry *entry=cache->entries+(hash&511);
    int hit=entry->valid && memcmp(entry->key,key,sizeof(key))==0;
    if (hit) ++cache->hits;
    else { ++cache->misses; entry->valid=0; }
    for (int index=0;index<3;++index) for (int side=0;side<2;++side) {
        int row=2*index+side;
        double sign=side==0 ? -1. : 1.,direction[3];
        for (int j=0;j<3;++j) { normals[row][j]=sign*(j==index ? 1. : 0.); direction[j]=-normals[row][j]; }
        if (!hit && !support_values(direction,axis,radius,half_width,shoulder,crown,entry->offsets[row])) return 0;
        for (int j=0;j<3;++j) wheels[row][j]=center[j]+entry->offsets[row][j];
    }
    if (!hit) { memcpy(entry->key,key,sizeof(key)); entry->valid=1; }
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
    if (!lab_box_axis_values(self,center,axis,radius,half_width,shoulder,crown,normals,wheels)) goto error;
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
    if (!lab_box_axis_values(self,center,axis,radius,half_width,shoulder,crown,normals,wheels)) goto error;
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
    if (!lab_box_axis_values(self,center,axis,radius,half_width,shoulder,crown,normals,wheels)) goto error;
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
/* 原Rodrigues三个系数矩阵逐项准备；三角函数和矩阵乘法仍由原NumPy执行。 */
static PyObject *rotation_increment_terms_native(PyObject *self,PyObject *args) {
    PyObject *inputs,*outputs;
    double sine,one_minus_cosine;
    if (!PyArg_ParseTuple(args,"OOdd",&inputs,&outputs,&sine,&one_minus_cosine)) return NULL;
    const int dimensions[2]={1,2};
    const Py_ssize_t shapes[2][3]={{3},{9,3}};
    Py_buffer v[2]={{0}};
    if (!lab_buffers(inputs,outputs,v,1,1,dimensions,shapes,-1,-1)) goto error;
    double x=lab_get(v,0,0),y=lab_get(v,1,0),z=lab_get(v,2,0);
    double skew[3][3]={{0.,-z,y},{z,0.,-x},{-y,x,0.}};
    for (int i=0;i<3;++i) for (int j=0;j<3;++j) {
        lab_set(v+1,i,j,skew[i][j]);
        lab_set(v+1,3+i,j,(i==j ? 1. : 0.)+sine*skew[i][j]);
        lab_set(v+1,6+i,j,one_minus_cosine*skew[i][j]);
    }
    lab_release(v,2); Py_RETURN_NONE;
error:
    lab_release(v,2); return NULL;
}

/* 四轮保留原减法/乘法/加法及NumPy普通叉积顺序；输出布局由调用者按原矩阵分配。 */
static PyObject *finite_motion_vectors_native(PyObject *self,PyObject *args) {
    PyObject *inputs,*outputs;
    double h;
    if (!PyArg_ParseTuple(args,"OOd",&inputs,&outputs,&h)) return NULL;
    const int dimensions[7]={1,2,2,1,2,2,2};
    const Py_ssize_t shapes[7][3]={{3},{4,3},{4,3},{6},{4,3},{4,3},{4,3}};
    Py_buffer v[7]={{0}};
    if (!lab_buffers(inputs,outputs,v,4,3,dimensions,shapes,-1,-1)) goto error;
    double position[3],translation[3],angular[3];
    for (int j=0;j<3;++j) {
        position[j]=lab_get(v,j,0); translation[j]=lab_get(v+3,j,0); angular[j]=lab_get(v+3,3+j,0);
    }
    for (int i=0;i<4;++i) {
        double difference[3],arms[3],product[3];
        for (int j=0;j<3;++j) {
            double old_arm=lab_get(v+1,i,j)-position[j];
            difference[j]=lab_get(v+2,i,j)-translation[j];
            double change=h*difference[j];
            arms[j]=old_arm+change;
            lab_set(v+4,i,j,old_arm); lab_set(v+5,i,j,change);
        }
        cross_regular(angular,arms,product);
        for (int j=0;j<3;++j) lab_set(v+6,i,j,difference[j]-product[j]);
    }
    lab_release(v,7); Py_RETURN_NONE;
error:
    lab_release(v,7); return NULL;
}
/* 保留原端口反力、轮端滚阻与16维动量的逐项减/乘/减顺序；尾部由原材料和端口填写。 */
static PyObject *unsprung_momentum_values_native(PyObject *self,PyObject *args) {
    PyObject *inputs,*outputs;
    double dt;
    if (!PyArg_ParseTuple(args,"OOd",&inputs,&outputs,&dt)) return NULL;
    const int dimensions[7]={1,1,1,1,1,1,1};
    const Py_ssize_t shapes[7][3]={{16},{16},{4},{16},{16},{16},{34}};
    Py_buffer v[7]={{0}};
    if (!lab_buffers(inputs,outputs,v,5,2,dimensions,shapes,-1,-1)) goto error;
    for (int i=0;i<16;++i) {
        double reaction=lab_get(v,i,0)-lab_get(v+1,i,0);
        if (i>=12) reaction-=lab_get(v+2,i-12,0);
        double momentum=lab_get(v+4,i,0)-dt*(reaction-lab_get(v+3,i,0));
        lab_set(v+5,i,0,reaction); lab_set(v+6,i,0,momentum);
    }
    lab_release(v,7); Py_RETURN_NONE;
error:
    lab_release(v,7); return NULL;
}
/* 四轮仍调用原rotated_path_values；只合并Python向量/返回元组的四次包装。 */
static PyObject *finite_contact_averages_native(PyObject *self,PyObject *args) {
    PyObject *inputs,*outputs;
    double angle;
    if (!PyArg_ParseTuple(args,"OOd",&inputs,&outputs,&angle)) return NULL;
    const int dimensions[3]={2,1,2};
    const Py_ssize_t shapes[3][3]={{4,3},{3},{4,3}};
    Py_buffer v[3]={{0}};
    if (!lab_buffers(inputs,outputs,v,2,1,dimensions,shapes,-1,-1)) goto error;
    double axis[3];
    for (int j=0;j<3;++j) axis[j]=lab_get(v+1,j,0);
    for (int i=0;i<4;++i) {
        double value[3],end[3],average[3];
        lab_row(v,i,value);
        rotated_path_values(value,axis,angle,1.,end,average);
        if (PyErr_Occurred()) goto error;
        for (int j=0;j<3;++j) lab_set(v+2,i,j,average[j]);
    }
    lab_release(v,3); Py_RETURN_NONE;
error:
    lab_release(v,3); return NULL;
}
/* 原三个顺序累加、平方与法向转向速度；不改变接触基或弹性储能模型。 */
static PyObject *finite_contact_frames_native(PyObject *self,PyObject *args) {
    PyObject *inputs,*outputs;
    double h,half_stiffness;
    if (!PyArg_ParseTuple(args,"OOdd",&inputs,&outputs,&h,&half_stiffness)) return NULL;
    const int dimensions[11]={2,2,2,2,1,1,1,2,2,1,2};
    const Py_ssize_t shapes[11][3]={{4,3},{4,3},{4,3},{4,3},{4},{4},{4},{4,3},{4,2},{4},{4,3}};
    Py_buffer v[11]={{0}};
    if (!lab_buffers(inputs,outputs,v,8,3,dimensions,shapes,-1,-1)) goto error;
    for (int i=0;i<4;++i) {
        double previous[3],projection[3];
        lab_row(v,i,previous);
        for (int k=0;k<3;++k) {
            double axis[3];
            lab_row(v+1+k,i,axis);
            projection[k]=lab_dot(previous,axis);
        }
        lab_set(v+8,i,0,projection[0]); lab_set(v+8,i,1,projection[1]);
        lab_set(v+9,i,0,half_stiffness*pow(projection[2],2.));
        for (int j=0;j<2;++j) lab_set(v+10,i,j,lab_get(v+7,i,j));
        double change=-(lab_get(v+4,i,0)-lab_get(v+5,i,0));
        lab_set(v+10,i,2,change/(h*lab_get(v+6,i,0)));
    }
    lab_release(v,11); Py_RETURN_NONE;
error:
    lab_release(v,11); return NULL;
}
/* 普通三维叉积按原两个乘法、一次减法；不能替换为补偿叉积或融合乘加。 */
static PyObject *ordinary_cross_rows_native(PyObject *self,PyObject *args) {
    PyObject *inputs,*outputs;
    Py_ssize_t first,second;
    if (!PyArg_ParseTuple(args,"OOnn",&inputs,&outputs,&first,&second)) return NULL;
    Py_ssize_t count=first==1 ? second : first;
    if (first<0 || second<0 || count>INT_MAX || (first!=1 && first!=count) || (second!=1 && second!=count)) {
        PyErr_SetString(PyExc_ValueError,"三维叉积行数不能广播或超出本机索引范围"); return NULL;
    }
    const int dimensions[3]={2,2,2};
    const Py_ssize_t shapes[3][3]={{first,3},{second,3},{count,3}};
    Py_buffer v[3]={{0}};
    if (!lab_buffers(inputs,outputs,v,2,1,dimensions,shapes,-1,-1)) goto error;
    for (int i=0;i<count;++i) {
        double a[3],b[3],product[3];
        lab_row(v,first==1 ? 0 : i,a); lab_row(v+1,second==1 ? 0 : i,b);
        cross_regular(a,b,product);
        for (int j=0;j<3;++j) lab_set(v+2,i,j,product[j]);
    }
    lab_release(v,3); Py_RETURN_NONE;
error:
    lab_release(v,3); return NULL;
}
/* 二/三维实数范数仍为原逐项点积后开方，不能改用hypot或补偿求和。 */
static PyObject *ordinary_small_norm_native(PyObject *self,PyObject *object) {
    Py_buffer view={0};
    if (PyObject_GetBuffer(object,&view,PyBUF_STRIDES|PyBUF_FORMAT)<0) return NULL;
    if (view.ndim!=1 || view.itemsize!=sizeof(double) || strcmp(view.format,"d")
        || (view.shape[0]!=2 && view.shape[0]!=3)) {
        PyErr_SetString(PyExc_ValueError,"接触几何范数须为二/三维本机双精度向量");
        PyBuffer_Release(&view); return NULL;
    }
    double squared=0.;
    for (int i=0;i<view.shape[0];++i) {
        double value=lab_get(&view,i,0);
        squared+=value*value;
    }
    PyBuffer_Release(&view);
    return PyFloat_FromDouble(sqrt(squared));
}
/* 原四棱的长度/临界值/投影界限，不改变驻点证明或52轮细化。 */
static PyObject *box_edge_proof_native(PyObject *self,PyObject *args) {
    PyObject *inputs,*outputs;
    double first;
    if (!PyArg_ParseTuple(args,"OOd",&inputs,&outputs,&first)) return NULL;
    const int dimensions[2]={2,2};
    const Py_ssize_t shapes[2][3]={{4,2},{4,3}};
    Py_buffer v[2]={{0}};
    if (!lab_buffers(inputs,outputs,v,1,1,dimensions,shapes,-1,-1)) goto error;
    for (int row=0;row<4;++row) {
        double a=lab_get(v,row,0),b=lab_get(v,row,1);
        double length=sqrt((0.+a*a)+b*b),squared=length*length-first*first;
        double minimum=b<a ? b : a,maximum=b>a ? b : a;
        double negative_a=a<0. ? a : 0.,negative_b=b<0. ? b : 0.;
        double positive_a=a>0. ? a : 0.,positive_b=b>0. ? b : 0.;
        double low=minimum<0. ? -sqrt((0.+negative_a*negative_a)+negative_b*negative_b) : minimum;
        double high=maximum>0. ? sqrt((0.+positive_a*positive_a)+positive_b*positive_b) : maximum;
        lab_set(v+1,row,0,sqrt(squared<0. ? 0. : squared));
        lab_set(v+1,row,1,low);lab_set(v+1,row,2,high);
    }
    lab_release(v,2); Py_RETURN_NONE;
error:
    lab_release(v,2); return NULL;
}
/* 仍按原轮心/表面次序调用真实查询；只有完整成功的候选元组才进入本子步缓存。 */
static PyObject *radial_surface_candidates(PyObject *surface,PyObject *values,Py_ssize_t row,
        PyObject *center,PyObject *axis,PyObject *config,PyObject *cache,PyObject *key,PyObject *query_name) {
    if (values!=Py_None) {
        PyObject *value=PySequence_GetItem(values,row);
        if (!value) return NULL;
        PyObject *result=PyTuple_Pack(1,value); Py_DECREF(value); return result;
    }
    PyObject *arguments[4]={surface,center,axis,config};
    if (cache==Py_None) return PyObject_VectorcallMethod(query_name,arguments,4,NULL);
    PyObject *cached=PyDict_GetItemWithError(cache,key);
    if (cached && cached!=Py_None) return Py_NewRef(cached);
    if (PyErr_Occurred()) return NULL;
    PyObject *query=PyObject_VectorcallMethod(query_name,arguments,4,NULL);
    if (!query) return NULL;
    PyObject *result=PySequence_Tuple(query); Py_DECREF(query);
    if (result && PyDict_SetItem(cache,key,result)<0) Py_CLEAR(result);
    return result;
}
static int radial_candidate_best(PyObject *candidate,PyObject *surface,PyObject *limit,
        PyObject *slope,PyObject *vertical,PyObject *body_name,PyObject **best) {
    PyObject *fields=PySequence_Fast(candidate,"真实接触候选须为四项");
    if (!fields) return 0;
    if (PySequence_Fast_GET_SIZE(fields)!=4) {
        PyErr_SetString(PyExc_ValueError,"真实接触候选须为距离/法线/见证点/平面四项");
        Py_DECREF(fields); return 0;
    }
    PyObject **parts=PySequence_Fast_ITEMS(fields);
    int eligible=PyObject_RichCompareBool(parts[0],limit,Py_LE);
    if (eligible>0) {
        PyObject *component=PyObject_GetItem(parts[1],vertical);
        if (!component) { Py_DECREF(fields); return 0; }
        eligible=PyObject_RichCompareBool(component,slope,Py_GE); Py_DECREF(component);
    }
    if (eligible>0 && *best) eligible=PyObject_RichCompareBool(parts[0],PyTuple_GET_ITEM(*best,0),Py_LT);
    if (eligible>0) {
        PyObject *body=PyObject_GetAttr(surface,body_name);
        if (!body) { Py_DECREF(fields); return 0; }
        PyObject *next=PyTuple_Pack(5,parts[0],parts[1],parts[2],body,parts[3]); Py_DECREF(body);
        if (!next) { Py_DECREF(fields); return 0; }
        Py_XSETREF(*best,next);
    }
    Py_DECREF(fields); return eligible>=0;
}
static PyObject *radial_selected_hit(PyObject *best,PyObject *hit_type,Py_buffer *outputs,int row) {
    if (!best) return Py_NewRef(Py_None);
    PyObject *distance=PyTuple_GET_ITEM(best,0),*normal=PyTuple_GET_ITEM(best,1),*point=PyTuple_GET_ITEM(best,2);
    PyObject *point_tuple=PySequence_Tuple(point),*normal_tuple=PySequence_Tuple(normal);
    if (!point_tuple || !normal_tuple) { Py_XDECREF(point_tuple); Py_XDECREF(normal_tuple); return NULL; }
    double normal_values[3],point_values[3],number=PyFloat_AsDouble(distance);
    if (PyErr_Occurred() || !vector(normal_tuple,normal_values) || !vector(point_tuple,point_values)) {
        Py_DECREF(point_tuple); Py_DECREF(normal_tuple); return NULL;
    }
    lab_set(outputs,row,0,1.); lab_set(outputs+1,row,0,number);
    for (int j=0;j<3;++j) { lab_set(outputs+2,row,j,point_values[j]); lab_set(outputs+3,row,j,normal_values[j]); }
    PyObject *hit=PyObject_CallFunctionObjArgs(hit_type,PyTuple_GET_ITEM(best,3),point_tuple,normal_tuple,PyTuple_GET_ITEM(best,4),NULL);
    Py_DECREF(point_tuple); Py_DECREF(normal_tuple); return hit;
}
static PyObject *radial_query_hits_native(PyObject *self,PyObject *args) {
    PyObject *objects,*outputs;
    Py_ssize_t count;
    if (!PyArg_ParseTuple(args,"OOn",&objects,&outputs,&count)) return NULL;
    if (!PyTuple_Check(objects) || PyTuple_GET_SIZE(objects)!=9 || count<0 || count>INT_MAX) {
        PyErr_SetString(PyExc_ValueError,"真实接触遍历参数数量或轮心数不符"); return NULL;
    }
    PyObject *surfaces=NULL,*planes=NULL,*caches=NULL,*centers=NULL,*axes=NULL,*center=NULL,*axis=NULL;
    PyObject *candidates=NULL,*iterator=NULL,*candidate=NULL,*best=NULL,*hits=NULL,*slope=NULL,*vertical=NULL;
    PyObject *query_name=NULL,*body_name=NULL;
    PyObject *empty=PyTuple_New(0);
    const int dimensions[4]={1,1,2,2};
    const Py_ssize_t shapes[4][3]={{count},{count},{count,3},{count,3}};
    Py_buffer v[4]={{0}};
    if (!empty || !lab_buffers(empty,outputs,v,0,4,dimensions,shapes,-1,-1)) goto error;
    Py_CLEAR(empty);
    surfaces=PySequence_Fast(PyTuple_GET_ITEM(objects,0),"真实表面须为序列");
    planes=PySequence_Fast(PyTuple_GET_ITEM(objects,1),"真实平面候选须为序列");
    if (!surfaces || !planes) goto error;
    Py_ssize_t surface_count=PySequence_Fast_GET_SIZE(surfaces);
    if (PySequence_Fast_GET_SIZE(planes)!=surface_count) {
        PyErr_SetString(PyExc_ValueError,"真实表面和平面候选数量不符"); goto error;
    }
    PyObject *keys=PyTuple_GET_ITEM(objects,4),*cache_input=PyTuple_GET_ITEM(objects,5);
    PyObject *config=PyTuple_GET_ITEM(objects,6),*hit_type=PyTuple_GET_ITEM(objects,7),*limit=PyTuple_GET_ITEM(objects,8);
    if (cache_input!=Py_None) {
        caches=PySequence_Fast(cache_input,"本子步表面缓存须为序列");
        if (!caches) goto error;
        if (!PyTuple_Check(keys) || PyTuple_GET_SIZE(keys)!=count || PySequence_Fast_GET_SIZE(caches)!=surface_count) {
            PyErr_SetString(PyExc_ValueError,"本子步几何键/缓存数量不符"); goto error;
        }
        for (Py_ssize_t i=0;i<surface_count;++i) if (!PyDict_Check(PySequence_Fast_GET_ITEM(caches,i))) {
            PyErr_SetString(PyExc_ValueError,"本子步表面缓存须为字典"); goto error;
        }
    }
    centers=PyObject_GetIter(PyTuple_GET_ITEM(objects,2)); axes=PyObject_GetIter(PyTuple_GET_ITEM(objects,3));
    hits=PyList_New(0); slope=PyFloat_FromDouble(.5); vertical=PyLong_FromLong(2);
    query_name=PyUnicode_InternFromString("query"); body_name=PyUnicode_InternFromString("body");
    if (!centers || !axes || !hits || !slope || !vertical || !query_name || !body_name) goto error;
    for (int row=0;row<count;++row) {
        center=PyIter_Next(centers);
        if (!center) { if (PyErr_Occurred()) goto error; break; }
        axis=PyIter_Next(axes);
        if (!axis) { if (PyErr_Occurred()) goto error; Py_CLEAR(center); break; }
        for (Py_ssize_t index=0;index<surface_count;++index) {
            PyObject *surface=PySequence_Fast_GET_ITEM(surfaces,index),*values=PySequence_Fast_GET_ITEM(planes,index);
            PyObject *cache=caches ? PySequence_Fast_GET_ITEM(caches,index) : Py_None;
            PyObject *key=caches ? PyTuple_GET_ITEM(keys,row) : Py_None;
            candidates=radial_surface_candidates(surface,values,row,center,axis,config,cache,key,query_name);
            if (!candidates) goto error;
            iterator=PyObject_GetIter(candidates); Py_CLEAR(candidates);
            if (!iterator) goto error;
            while ((candidate=PyIter_Next(iterator))) {
                if (!radial_candidate_best(candidate,surface,limit,slope,vertical,body_name,&best)) goto error;
                Py_CLEAR(candidate);
            }
            if (PyErr_Occurred()) goto error;
            Py_CLEAR(iterator);
        }
        PyObject *hit=radial_selected_hit(best,hit_type,v,row);
        if (!hit) goto error;
        int added=PyList_Append(hits,hit); Py_DECREF(hit);
        if (added<0) goto error;
        Py_CLEAR(best); Py_CLEAR(center); Py_CLEAR(axis);
    }
    lab_release(v,4); Py_DECREF(surfaces); Py_DECREF(planes); Py_XDECREF(caches);
    Py_DECREF(centers); Py_DECREF(axes); Py_DECREF(slope); Py_DECREF(vertical);
    Py_DECREF(query_name); Py_DECREF(body_name); return hits;
error:
    lab_release(v,4); Py_XDECREF(empty); Py_XDECREF(surfaces); Py_XDECREF(planes); Py_XDECREF(caches);
    Py_XDECREF(centers); Py_XDECREF(axes); Py_XDECREF(center); Py_XDECREF(axis); Py_XDECREF(candidates);
    Py_XDECREF(iterator); Py_XDECREF(candidate); Py_XDECREF(best); Py_XDECREF(hits); Py_XDECREF(slope); Py_XDECREF(vertical);
    Py_XDECREF(query_name); Py_XDECREF(body_name);
    return NULL;
}
#endif
