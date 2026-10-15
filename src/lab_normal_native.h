#ifndef COASTAL_LAB_NORMAL_NATIVE_H
#define COASTAL_LAB_NORMAL_NATIVE_H

/* 仅保存已验证的不可变硬件和曲线；不持有世界、构型或积分状态。 */
typedef struct {
    int count;
    double *q,*x,*m,*square,*cubic,reference;
} LabNormalCurve;
typedef struct {
    double rates[4],bars[2],stops[4],travel,preloads[4],compression[4],extension[4];
    int coil,installation,nonlinear_damper;
    LabNormalCurve spring[4],damper[4],force[4];
} LabNormalParameters;

static void lab_normal_free(LabNormalParameters *p) {
    for (int i=0;i<4;++i) {
        PyMem_Free(p->spring[i].q); PyMem_Free(p->damper[i].q); PyMem_Free(p->force[i].q);
    }
    PyMem_Free(p);
}
static void lab_normal_destroy(PyObject *capsule) {
    lab_normal_free(PyCapsule_GetPointer(capsule,"CoastalDrive.LabNormalParameters"));
}
static int lab_normal_curve(PyObject *object,LabNormalCurve *curve,int installation) {
    int fields=installation ? 4 : 2;
    if (!PyTuple_Check(object) || PyTuple_GET_SIZE(object)!=fields) {
        PyErr_SetString(PyExc_ValueError,"法向材料曲线字段不符"); return 0;
    }
    PyObject *q=PyTuple_GET_ITEM(object,0);
    Py_ssize_t count=PySequence_Size(q);
    if (count<0) return 0;
    if (count<2 || count>INT_MAX/5) { PyErr_SetString(PyExc_ValueError,"法向材料曲线节点数不符"); return 0; }
    curve->count=(int)count;
    curve->q=PyMem_Calloc(5*(size_t)count,sizeof(double));
    if (!curve->q) { PyErr_NoMemory(); return 0; }
    curve->x=curve->q+count; curve->m=curve->x+count;
    curve->square=curve->m+count; curve->cubic=curve->square+count;
    if (!vector(q,curve->q,(int)count) || !vector(PyTuple_GET_ITEM(object,1),curve->x,(int)count)) return 0;
    if (installation) {
        if (!vector(PyTuple_GET_ITEM(object,2),curve->m,(int)count)) return 0;
        curve->reference=PyFloat_AsDouble(PyTuple_GET_ITEM(object,3));
        if (PyErr_Occurred()) return 0;
        if (curve->reference==0.) { PyErr_SetString(PyExc_ZeroDivisionError,"安装参考运动比不能为零"); return 0; }
    }
    for (int i=0;i<count-1;++i) {
        double h=curve->q[i+1]-curve->q[i];
        if (!(h>0.)) { PyErr_SetString(PyExc_ValueError,"法向材料曲线坐标须递增"); return 0; }
        double secant=(curve->x[i+1]-curve->x[i])/h;
        if (installation) {
            curve->cubic[i]=(curve->m[i]+curve->m[i+1]-2*secant)/(h*h);
            curve->square[i]=(3*secant-2*curve->m[i]-curve->m[i+1])/h;
        } else curve->m[i]=secant;
    }
    return 1;
}
static int lab_normal_curves(PyObject *objects,LabNormalCurve curves[4],int installation) {
    if (!PyTuple_Check(objects) || PyTuple_GET_SIZE(objects)!=4) {
        PyErr_SetString(PyExc_ValueError,"法向材料须有四轮曲线"); return 0;
    }
    for (int i=0;i<4;++i) if (!lab_normal_curve(PyTuple_GET_ITEM(objects,i),curves+i,installation)) return 0;
    return 1;
}
static PyObject *unsprung_normal_parameters_native(PyObject *self,PyObject *args) {
    PyObject *rates,*bars,*stops,*preloads,*compression,*extension,*spring,*damper,*force;
    LabNormalParameters *p=PyMem_Calloc(1,sizeof(*p));
    if (!p) return PyErr_NoMemory();
    if (!PyArg_ParseTuple(args,"OOOdpOOOOOO",&rates,&bars,&stops,&p->travel,&p->coil,&preloads,&compression,&extension,
        &spring,&damper,&force)) goto error;
    if (!vector(rates,p->rates,4) || !vector(bars,p->bars,2) || !vector(stops,p->stops,4)
        || !vector(preloads,p->preloads,4) || !vector(compression,p->compression,4) || !vector(extension,p->extension,4)) goto error;
    p->installation=spring!=Py_None; p->nonlinear_damper=force!=Py_None;
    if ((spring==Py_None)!=(damper==Py_None)) { PyErr_SetString(PyExc_ValueError,"安装曲线须成对提供"); goto error; }
    if (p->installation && (!lab_normal_curves(spring,p->spring,1) || !lab_normal_curves(damper,p->damper,1))) goto error;
    if (p->nonlinear_damper && !lab_normal_curves(force,p->force,0)) goto error;
    PyObject *capsule=PyCapsule_New(p,"CoastalDrive.LabNormalParameters",lab_normal_destroy);
    if (!capsule) goto error;
    return capsule;
error:
    lab_normal_free(p); return NULL;
}

/* 二分与原bisect_right相同；端点保留原区间选择，域外沿端点切线外推。 */
static int lab_normal_interval(const LabNormalCurve *curve,double q) {
    int lo=0,hi=curve->count;
    while (lo<hi) { int middle=lo+(hi-lo)/2; if (q<curve->q[middle]) hi=middle; else lo=middle+1; }
    int index=lo-1;
    if (index<0) index=0;
    if (index>curve->count-2) index=curve->count-2;
    return index;
}
static void lab_normal_installation(const LabNormalCurve *curve,double q,double *position,double *ratio,double *gradient) {
    if (q<curve->q[0] || q>curve->q[curve->count-1]) {
        int end=q<curve->q[0] ? 0 : curve->count-1;
        *position=curve->x[end]+curve->m[end]*(q-curve->q[end]); *ratio=curve->m[end]; *gradient=0.;
    } else {
        int i=lab_normal_interval(curve,q);
        double t=q-curve->q[i],square=curve->square[i],cubic=curve->cubic[i],m=curve->m[i];
        *position=curve->x[i]+t*(m+t*(square+t*cubic));
        *ratio=m+t*(2*square+3*t*cubic); *gradient=2*square+6*t*cubic;
    }
    *position/=curve->reference; *ratio/=curve->reference; *gradient/=curve->reference;
}
static double lab_normal_positive(double value) {
    if (isnan(value)) return value;
    return value>0. ? value : 0.;
}
static void lab_normal_store(Py_buffer *v,int row,int column,double value) {
    memcpy((char *)v->buf+row*v->strides[0]+column*v->strides[1],&value,sizeof(value));
}

/* 保留原四轮标量顺序；四个能量dot仍交由Python的原NumPy入口完成。 */
static PyObject *unsprung_normal_material_native(PyObject *self,PyObject *args) {
    PyObject *capsule,*inputs,*output;
    double dt;
    if (!PyArg_ParseTuple(args,"OOOd",&capsule,&inputs,&output,&dt)) return NULL;
    LabNormalParameters *p=PyCapsule_GetPointer(capsule,"CoastalDrive.LabNormalParameters");
    if (!p) return NULL;
    const int dimensions[7]={1,1,1,1,1,1,2};
    const Py_ssize_t shapes[7][2]={{4},{4},{4},{4},{4},{4},{13,4}};
    Py_buffer v[7]={{0}};
    if (!lab_joint_buffers(inputs,output,v,6,dimensions,shapes)) goto error;
    double q[4],velocity[4],rates[4],spring,bar[2],stop,force[4],tangent[4],damper_speed[4],damper_travel[4];
    for (int i=0;i<4;++i) { q[i]=lab_joint_get(v,i,0); velocity[i]=lab_joint_get(v+1,i,0); rates[i]=p->coil ? 0. : p->rates[i]; }
    suspension_elastic_values(q,rates,p->bars,p->stops,p->travel,&spring,bar,&stop,force);
    for (int i=0;i<4;++i) {
        double position=q[i],ratio=1.,gradient=0.,active=0.;
        tangent[i]=p->rates[i];
        if (p->coil) {
            if (p->installation) lab_normal_installation(p->spring+i,q[i],&position,&ratio,&gradient);
            double shifted=position+p->preloads[i]/p->rates[i];
            active=lab_normal_positive(shifted);
            force[i]+=p->rates[i]*active*ratio;
            tangent[i]=shifted>0. ? p->rates[i]*(ratio*ratio+active*gradient) : 0.;
        }
        lab_normal_store(v+6,8,i,active*active);
        position=q[i]; ratio=1.; gradient=0.;
        if (p->installation) lab_normal_installation(p->damper+i,q[i],&position,&ratio,&gradient);
        double damper;
        if (p->nonlinear_damper) {
            const LabNormalCurve *curve=p->force+i;
            double speed=ratio*velocity[i]; int index=lab_normal_interval(curve,speed);
            double slope=curve->m[index],value=curve->x[index]+slope*(speed-curve->q[index]);
            damper=ratio*value; damper_speed[i]=ratio*ratio*slope;
            damper_travel[i]=gradient*(value+ratio*velocity[i]*slope);
        } else {
            double coefficient=velocity[i]>=0. ? p->compression[i] : p->extension[i],derivative=0.;
            if (p->installation) { derivative=2*coefficient*ratio*gradient; coefficient=coefficient*(ratio*ratio); }
            damper=coefficient*velocity[i]; damper_speed[i]=coefficient; damper_travel[i]=derivative*velocity[i];
        }
        double positive=lab_normal_positive(lab_joint_get(v+2,i,0));
        double delta_rate=(positive-lab_normal_positive(lab_joint_get(v+3,i,0)))/dt;
        double radial_rate=lab_joint_get(v+4,i,0),damping=lab_joint_get(v+5,i,0);
        double trial=radial_rate*positive+damping*delta_rate;
        int contact=lab_joint_get(v+2,i,0)>0. && trial>0.;
        lab_normal_store(v+6,0,i,force[i]+damper); lab_normal_store(v+6,1,i,contact ? trial : 0.);
        lab_normal_store(v+6,2,i,force[i]); lab_normal_store(v+6,3,i,contact ? dt*radial_rate+damping : 0.);
        lab_normal_store(v+6,9,i,positive*positive); lab_normal_store(v+6,10,i,damper);
        lab_normal_store(v+6,11,i,contact ? damping : 0.); lab_normal_store(v+6,12,i,delta_rate*delta_rate);
    }
    double hessian[16]={0.};
    for (int i=0;i<4;++i) hessian[4*i+i]=tangent[i];
    for (int axle=0;axle<2;++axle) {
        int left=2*axle,right=left+1;
        hessian[4*left+left]+=p->bars[axle]; hessian[4*right+right]+=p->bars[axle];
        hessian[4*left+right]-=p->bars[axle]; hessian[4*right+left]-=p->bars[axle];
    }
    for (int i=0;i<4;++i) for (int j=0;j<4;++j) {
        double stop_tangent=i==j && fabs(q[i])>p->travel ? p->stops[i] : 0.;
        double diagonal=i==j ? damper_speed[i]+dt*damper_travel[i] : 0.;
        lab_normal_store(v+6,4+i,j,dt*(hessian[4*i+j]+stop_tangent)+diagonal);
    }
    lab_joint_release(v,7);
    return Py_BuildValue("(d(dd)d)",spring,bar[0],bar[1],stop);
error:
    lab_joint_release(v,7); return NULL;
}
#endif
