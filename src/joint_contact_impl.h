#include "joint_contact_api.h"
typedef struct {
    int (*cast_points)(const void *wheel_ptr, const void *target_ptr,
                       const double from_pose[7], const double to_pose[7],
                       const double body_pose[7], const double shape_pose[7],
                       float ceiling, float *fraction_out, float normal_out[3], float point_out[3]);
    void (*hull_bounds)(const void *target_ptr, const double body_pose[7],
                        const double shape_pose[7], double low_out[3], double high_out[3]);
    const char *capsule_name;
} JointConvexCastApi;
typedef struct {
    const void *hull;
    double body_pose[7], shape_pose[7];
    double low[3], high[3];
    int group;
} JointHullPart;
typedef struct {
    int present;
    double hub[3],direction[3],normal[3],point[3],length;
    double axis[3],origin[3],low[3],high[3],radius,reach,width,shoulder,crown;
    SurfacePacket *surfaces;
    SurfacePacket *complete;
    SurfacePacket *candidate;
    double candidate_low[3],candidate_high[3];
    const void *wheel_hull;
    JointHullPart *hulls;
    Py_ssize_t hull_count;
} JointPlane;
typedef struct {
    JointPlane planes[4];
    double damping;
    PyObject *complete_owners, *hull_owners, *query;
    const JointConvexCastApi *convex_api;
} JointContacts;
static void joint_candidate_free(SurfacePacket *packet) {
    PyMem_RawFree(packet->parts);PyMem_RawFree(packet);
}


static double joint_fsum(const double *values,int count) {
    double partials[16],hi=0.,lo=0.; int n=0;
    for(int k=0;k<count;++k) {
        double x=values[k]; int write=0;
        for(int j=0;j<n;++j) {
            double y=partials[j]; if(fabs(x)<fabs(y)){double swap=x;x=y;y=swap;}
            hi=x+y;lo=y-(hi-x);if(lo!=0.)partials[write++]=lo;x=hi;
        }
        n=write;if(x!=0.)partials[n++]=x;
    }
    if(n){hi=partials[--n];while(n){double x=hi,y=partials[--n];hi=x+y;lo=y-(hi-x);if(lo!=0.)break;}
        if(n&&((lo<0.&&partials[n-1]<0.)||(lo>0.&&partials[n-1]>0.))){double y=lo*2,x=hi+y;if(y==x-hi)hi=x;}}
    else hi=0.; return hi;
}

static int joint_pose7(PyObject *obj, double out[7]) {
    if (!PyTuple_Check(obj) || PyTuple_GET_SIZE(obj) != 7) {
        PyErr_SetString(PyExc_ValueError, "凸体姿态须为七元组");
        return 0;
    }
    for (int i = 0; i < 7; ++i) {
        out[i] = PyFloat_AsDouble(PyTuple_GET_ITEM(obj, i));
        if (PyErr_Occurred()) return 0;
    }
    return 1;
}

static const JointConvexCastApi *joint_convex_api(void) {
    static const JointConvexCastApi *cached = NULL;
    if (!cached) {
        PyObject *mod = PyImport_ImportModule("convex_cast_kernels");
        if (!mod) return NULL;
        PyObject *cap = PyObject_GetAttrString(mod, "_convex_cast_api");
        Py_DECREF(mod);
        if (!cap) return NULL;
        cached = (const JointConvexCastApi *)PyCapsule_GetPointer(cap, "CoastalDrive.convex_cast_api.v1");
        Py_DECREF(cap);
    }
    return cached;
}

static void joint_contacts_free(PyObject *capsule) {
    JointContacts *data=PyCapsule_GetPointer(capsule,JOINT_CONTACT_PACKET_NAME);
    if(!data)return;
    for(int i=0;i<4;++i){
        if(data->planes[i].surfaces)surface_packet_free(data->planes[i].surfaces);
        if(data->planes[i].candidate)joint_candidate_free(data->planes[i].candidate);
        if(data->planes[i].hulls)PyMem_RawFree(data->planes[i].hulls);
    }
    Py_XDECREF(data->complete_owners);
    Py_XDECREF(data->hull_owners);
    Py_XDECREF(data->query);
    PyMem_Free(data);
}

/* 原世界查询保留在持锁/GIL区；机械迭代仍用原共同数值内核。 */
static PyObject *joint_contact_query_prepare(PyObject *self,PyObject *query) {
    if(!PyCallable_Check(query)){PyErr_SetString(PyExc_TypeError,"有限接触查询必须可调用");return NULL;}
    JointContacts *data=PyMem_Calloc(1,sizeof(*data));if(!data)return PyErr_NoMemory();
    data->query=Py_NewRef(query);
    PyObject *capsule=PyCapsule_New(data,JOINT_CONTACT_PACKET_NAME,joint_contacts_free);
    if(!capsule){Py_DECREF(data->query);PyMem_Free(data);return NULL;}
    return capsule;
}
static int joint_contact_queries_world_values(void *packet) {
    return ((JointContacts *)packet)->query!=NULL;
}
static PyObject *joint_contact_queries_world(PyObject *self,PyObject *capsule) {
    JointContacts *data=PyCapsule_GetPointer(capsule,JOINT_CONTACT_PACKET_NAME);if(!data)return NULL;
    return PyBool_FromLong(joint_contact_queries_world_values(data));
}

static PyObject *joint_contact_prepare(PyObject *self,PyObject *args) {
    PyObject *contacts,*complete=Py_None,*hulls_arg=Py_None;double damping;
    if(!PyArg_ParseTuple(args,"Od|OO",&contacts,&damping,&complete,&hulls_arg))return NULL;
    if(PyTuple_Size(contacts)!=4){PyErr_SetString(PyExc_ValueError,"连续求解须为四轮接点");return NULL;}
    if(complete!=Py_None&&(!PyTuple_Check(complete)||PyTuple_GET_SIZE(complete)!=4)){
        PyErr_SetString(PyExc_ValueError,"完整几何须与四轮对应");return NULL;}
    if(hulls_arg!=Py_None&&(!PyTuple_Check(hulls_arg)||PyTuple_GET_SIZE(hulls_arg)!=4)){
        PyErr_SetString(PyExc_ValueError,"凸体几何须与四轮对应");return NULL;}
    JointContacts *data=PyMem_Calloc(1,sizeof(*data));if(!data)return PyErr_NoMemory();
    data->damping=damping;
    data->complete_owners=Py_NewRef(complete);
    data->hull_owners=Py_NewRef(hulls_arg);
    if(hulls_arg!=Py_None) {
        data->convex_api=joint_convex_api();
        if(!data->convex_api)goto failed;
    }
    for(int i=0;i<4;++i) {
        PyObject *contact=PyTuple_GET_ITEM(contacts,i);JointPlane *plane=&data->planes[i];
        if(contact==Py_None)continue;
        if(complete!=Py_None) {
            plane->complete=PyCapsule_GetPointer(PyTuple_GET_ITEM(complete,i),surface_packet_name);
            if(!plane->complete)goto failed;
        }
        if(hulls_arg!=Py_None) {
            PyObject *wheel_entry=PyTuple_GET_ITEM(hulls_arg,i);
            if(wheel_entry!=Py_None) {
                if(!PyTuple_Check(wheel_entry)||PyTuple_GET_SIZE(wheel_entry)!=2){
                    PyErr_SetString(PyExc_ValueError,"单轮凸体包须含轮冠与凸体组");goto failed;}
                PyObject *wh_cap=PyTuple_GET_ITEM(wheel_entry,0);
                PyObject *groups=PyTuple_GET_ITEM(wheel_entry,1);
                plane->wheel_hull=PyCapsule_GetPointer(wh_cap,data->convex_api->capsule_name);
                if(!plane->wheel_hull||!PyTuple_Check(groups))goto failed;
                Py_ssize_t total=0, ngroups=PyTuple_GET_SIZE(groups);
                for(Py_ssize_t g=0;g<ngroups;++g){
                    PyObject *grp=PyTuple_GET_ITEM(groups,g);
                    if(!PyTuple_Check(grp)){PyErr_SetString(PyExc_ValueError,"凸体组须为元组");goto failed;}
                    total+=PyTuple_GET_SIZE(grp);
                }
                if(total>0) {
                    plane->hulls=PyMem_RawMalloc((size_t)total*sizeof(JointHullPart));
                    if(!plane->hulls){PyErr_NoMemory();goto failed;}
                    Py_ssize_t pos=0;
                    for(Py_ssize_t g=0;g<ngroups;++g){
                        PyObject *grp=PyTuple_GET_ITEM(groups,g);
                        for(Py_ssize_t j=0;j<PyTuple_GET_SIZE(grp);++j){
                            PyObject *hg=PyTuple_GET_ITEM(grp,j);
                            PyObject *nat=PyObject_GetAttrString(hg,"native");
                            PyObject *bp=PyObject_GetAttrString(hg,"body_pose");
                            PyObject *sp=PyObject_GetAttrString(hg,"shape_pose");
                            int hok=nat&&bp&&sp;
                            if(hok){
                                plane->hulls[pos].hull=PyCapsule_GetPointer(nat,data->convex_api->capsule_name);
                                hok=plane->hulls[pos].hull&&joint_pose7(bp,plane->hulls[pos].body_pose)&&joint_pose7(sp,plane->hulls[pos].shape_pose);
                                if(hok)data->convex_api->hull_bounds(plane->hulls[pos].hull,plane->hulls[pos].body_pose,
                                                                     plane->hulls[pos].shape_pose,plane->hulls[pos].low,plane->hulls[pos].high);
                                plane->hulls[pos].group=(int)g;
                            }
                            Py_XDECREF(nat);Py_XDECREF(bp);Py_XDECREF(sp);
                            if(!hok)goto failed;
                            ++pos;
                        }
                    }
                    plane->hull_count=total;
                }
            }
        }
        PyObject *surface=PyObject_GetAttrString(contact,"surface");if(!surface)goto failed;
        PyObject *cache=PyObject_GetAttrString(surface,"candidates");
        int ok=cache&&vector_attribute(contact,"hub",plane->hub)&&vector_attribute(contact,"direction",plane->direction)
            &&vector_attribute(contact,"normal",plane->normal)&&vector_attribute(contact,"point",plane->point)
            &&double_attribute(contact,"length",&plane->length)&&vector_attribute(surface,"wheel_axis",plane->axis)
            &&vector_attribute(surface,"offset",plane->origin)&&double_attribute(surface,"wheel_radius",&plane->radius)
            &&double_attribute(surface,"reach",&plane->reach)&&double_attribute(surface,"width",&plane->width)
            &&double_attribute(surface,"shoulder",&plane->shoulder)&&double_attribute(surface,"crown",&plane->crown);
        if(ok) {
            PyObject *low=PyDict_GetItemString(cache,"low"),*high=PyDict_GetItemString(cache,"high");
            PyObject *surfaces=PyDict_GetItemString(cache,"surfaces");
            PyObject *empty=NULL;
            if(!low||!high||!surfaces) {
                /* 直接单车入口可没有覆盖盒缓存；仍查询已读取的完整真实世界。 */
                if(!plane->complete){PyErr_SetString(PyExc_ValueError,"有限接触没有候选或完整几何");ok=0;}
                else {for(int a=0;a<3;++a){plane->low[a]=INFINITY;plane->high[a]=-INFINITY;}
                    empty=PyList_New(0);surfaces=empty;if(!empty)ok=0;}
            } else ok=vector(low,plane->low)&&vector(high,plane->high);
            if(ok){PyObject *capsule=surface_packet_create(surfaces);if(!capsule)ok=0;
                else {plane->surfaces=PyCapsule_GetPointer(capsule,surface_packet_name);
                    PyCapsule_SetDestructor(capsule,NULL);Py_DECREF(capsule);plane->present=1;}}
            Py_XDECREF(empty);
        }
        Py_XDECREF(cache);Py_DECREF(surface);if(!ok)goto failed;
    }
    PyObject *result=PyCapsule_New(data,JOINT_CONTACT_PACKET_NAME,joint_contacts_free);
    if(!result)goto failed;
    return result;
failed:
    for(int i=0;i<4;++i){
        if(data->planes[i].surfaces)surface_packet_free(data->planes[i].surfaces);
        if(data->planes[i].candidate)joint_candidate_free(data->planes[i].candidate);
        if(data->planes[i].hulls)PyMem_RawFree(data->planes[i].hulls);
    }
    Py_XDECREF(data->complete_owners);
    Py_XDECREF(data->hull_owners);
    PyMem_Free(data);return NULL;
}


/* 只在覆盖盒越界时从本子步完整世界重筛；盒内保持所有可能接触的原序形状。 */
static int joint_complete_candidates(JointPlane *p,const double start[3],const double end[3]) {
    if(p->candidate) {
        int covered=1;
        for(int a=0;a<3;++a)if(fmin(start[a],end[a])<p->candidate_low[a]||fmax(start[a],end[a])>p->candidate_high[a])covered=0;
        if(covered)return 1;
    } else {
        SurfacePacket *candidate=PyMem_RawCalloc(1,sizeof(*candidate));if(!candidate){PyErr_NoMemory();return 0;}
        candidate->parts=PyMem_RawMalloc(p->complete->count*sizeof(*candidate->parts));
        if(p->complete->count&&!candidate->parts){PyMem_RawFree(candidate);PyErr_NoMemory();return 0;}
        p->candidate=candidate;
    }
    double center[3],half[3],envelope=p->radius+fabs(p->width)/2+fabs(p->shoulder)+fabs(p->crown);
    for(int a=0;a<3;++a) {
        p->candidate_low[a]=fmin(start[a],end[a])-.05;p->candidate_high[a]=fmax(start[a],end[a])+.05;
        center[a]=(p->candidate_low[a]+p->candidate_high[a])/2;half[a]=(p->candidate_high[a]-p->candidate_low[a])/2;
    }
    p->candidate->count=0;
    for(Py_ssize_t i=0;i<p->complete->count;++i) {
        SurfacePart *part=&p->complete->parts[i];int possible=1;
        if(part->kind!=0) {
            double offset[3],local_center[3],local_half[3];
            for(int a=0;a<3;++a) {
                double origin_terms[3],size_terms[3];
                for(int b=0;b<3;++b){origin_terms[b]=part->axes[a][b]*p->origin[b];size_terms[b]=fabs(part->axes[a][b])*half[b];}
                offset[a]=part->translation[a]+sum_three(origin_terms);local_half[a]=sum_three(size_terms)+envelope+part->margin;
            }
            transform_values(center,part->axes,offset,0,local_center);
            for(int a=0;a<3;++a) {
                double object_center=part->kind==2?part->triangles->center[a]:0.;
                double object_half=part->kind==2?part->triangles->half[a]:part->half[a];
                /* 包围盒只向外扩：补偿大坐标投影舍入，不改变任何精确接触阈值。 */
                double rounding=32*2.220446049250313e-16*(fabs(local_center[a])+fabs(offset[a])+fabs(object_center)+local_half[a]+object_half+1.);
                if(fabs(local_center[a]-object_center)>local_half[a]+object_half+rounding)possible=0;
            }
        }
        if(possible)p->candidate->parts[p->candidate->count++]=*part;
    }
    return 1;
}

/* 仅在原世界查询和结果解包期间接回同一个解释器线程状态。 */
static int joint_python_query(JointContacts *data,const double *velocity,const double *angular,double dt,
                             double *gradients,double *alignment,double *touching) {
    PyObject *result=PyObject_CallFunction(data->query,"(ddd)(ddd)d",velocity[0],velocity[1],velocity[2],
        angular[0],angular[1],angular[2],dt);
    if(!result)return 0;
    int ok=PyTuple_Check(result)&&PyTuple_GET_SIZE(result)==3;
    if(!ok)PyErr_SetString(PyExc_ValueError,"有限接触查询须返回梯度、对齐和接触四轮元组");
    if(ok)for(int j=0;j<3;++j)if(!PyTuple_Check(PyTuple_GET_ITEM(result,j))||PyTuple_GET_SIZE(PyTuple_GET_ITEM(result,j))!=4){
        PyErr_SetString(PyExc_ValueError,"有限接触查询须返回四轮结果");ok=0;break;}
    if(ok)for(int i=0;i<4;++i){
        PyObject *g=PyTuple_GET_ITEM(PyTuple_GET_ITEM(result,0),i);
        if(!PyTuple_Check(g)||PyTuple_GET_SIZE(g)!=6){PyErr_SetString(PyExc_ValueError,"接触梯度须为六维");ok=0;break;}
        for(int a=0;a<6;++a)gradients[6*i+a]=PyFloat_AsDouble(PyTuple_GET_ITEM(g,a));
        PyObject *aligned=PyTuple_GET_ITEM(PyTuple_GET_ITEM(result,1),i);
        alignment[i]=aligned==Py_None?0.:PyFloat_AsDouble(aligned);
        int present=PyObject_IsTrue(PyTuple_GET_ITEM(PyTuple_GET_ITEM(result,2),i));
        if(present<0||PyErr_Occurred()){ok=0;break;}touching[i]=present;
    }
    Py_DECREF(result);return ok;
}
static int joint_contact_evaluate(void *packet,const double *velocity,const double *angular,double dt,
                                 double *gradients,double *alignment,double *touching) {
    JointContacts *data=packet;double axis[3]={0.},angle=0.,scale=1.;
    if(data->query) {
        NativeSolveError *error=native_solve_error;
        if(error){
            PyEval_RestoreThread(error->thread_state);
            native_solve_error=NULL;*error->owner=NULL;
        }
        int ok=joint_python_query(data,velocity,angular,dt,gradients,alignment,touching);
        if(error){
            if(!ok)error->exception=PyErr_GetRaisedException();
            *error->owner=error;native_solve_error=error;
            PyEval_SaveThread();
        }
        return ok;
    }
    double omega[3]={angular[0],angular[1],angular[2]},v[3]={velocity[0],velocity[1],velocity[2]};
    double speed=sqrt(dot(omega,omega));
    if(speed!=0.) {
        double damped=speed*pow(1-data->damping,dt),limited=fmin(damped,3.14159265358979323846/(4*dt));
        double sine=limited<.001 ? dt/2-pow(dt,3.)*pow(limited,2.)/48 : sin(limited*dt/2)/limited;
        angle=2*atan2(damped*sine,cos(limited*dt/2));scale=angle/(dt*speed);
        for(int a=0;a<3;++a)axis[a]=omega[a]/speed;
    }
    for(int i=0;i<4;++i) {
        JointPlane *p=&data->planes[i];double *g=gradients+6*i;
        touching[i]=0.;alignment[i]=0.;memset(g,0,6*sizeof(double));if(!p->present)continue;
        double he[3],ha[3],de[3],da[3],we[3],wa[3],start[3],end[3];
        rotated_path_values(p->hub,axis,angle,scale,he,ha);
        rotated_path_values(p->direction,axis,angle,scale,de,da);
        rotated_path_values(p->axis,axis,angle,scale,we,wa);
        for(int a=0;a<3;++a){double hub=he[a]+dt*v[a];start[a]=hub-p->radius*de[a];end[a]=hub+p->reach*de[a];}
        double padding=p->radius+p->width/2+1e-5;
        SurfacePacket *selected=p->surfaces;
        for(int a=0;a<3;++a) {
            if(fmin(start[a],end[a])+p->origin[a]-padding<p->low[a]
                ||fmax(start[a],end[a])+p->origin[a]+padding>p->high[a]) {
                if(!p->complete){PyErr_SetString(PyExc_ArithmeticError,"连续有限接点缺少覆盖盒外的真实几何");return 0;}
                if(!joint_complete_candidates(p,start,end))return 0;
                selected=p->candidate;break;
            }
        }
        SurfaceEntry hit={0};
        if(!joint_surface_values(selected,start,end,we,p->origin,p->radius,p->width,p->shoulder,p->crown,&hit))return 0;
        if(p->hull_count>0&&p->wheel_hull&&data->convex_api) {
            double transverse=hypot(we[1],we[2]);
            double qr=1.,qi=0.,qj=0.,qk=0.;
            if(transverse!=0.) {
                double half=atan2(transverse,we[0])*.5,s=sin(half);
                qr=cos(half);qj=s*(-we[2]/transverse);qk=s*(we[1]/transverse);
            } else if(we[0]<0.) {
                qr=0.;qk=1.;
            }
            double from_pose[7]={start[0]+p->origin[0],start[1]+p->origin[1],start[2]+p->origin[2],qr,qi,qj,qk};
            double to_pose[7]={end[0]+p->origin[0],end[1]+p->origin[1],end[2]+p->origin[2],qr,qi,qj,qk};
            double w_low[3],w_high[3],w_pad=p->radius+p->width*0.5+p->shoulder+1e-3;
            for(int a=0;a<3;++a){
                w_low[a]=fmin(from_pose[a],to_pose[a])-w_pad;
                w_high[a]=fmax(from_pose[a],to_pose[a])+w_pad;
            }
            int best_found=0,cur_group=-1,grp_found=0;
            float best_frac=1.f,best_n[3]={0.f},best_p[3]={0.f};
            float grp_frac=1.f,grp_n[3]={0.f},grp_p[3]={0.f};
            for(Py_ssize_t h=0;h<p->hull_count;++h) {
                const JointHullPart *hp=&p->hulls[h];
                if(hp->group!=cur_group) {
                    if(grp_found&&(!best_found||grp_frac<best_frac)) {
                        best_found=1;best_frac=grp_frac;
                        memcpy(best_n,grp_n,sizeof(best_n));memcpy(best_p,grp_p,sizeof(best_p));
                    }
                    cur_group=hp->group;grp_found=0;grp_frac=1.f;
                }
                if(w_high[0]<hp->low[0]||w_low[0]>hp->high[0]
                   ||w_high[1]<hp->low[1]||w_low[1]>hp->high[1]
                   ||w_high[2]<hp->low[2]||w_low[2]>hp->high[2])
                    continue;
                float f,hn[3],pt[3];
                if(data->convex_api->cast_points(p->wheel_hull,hp->hull,from_pose,to_pose,
                                                 hp->body_pose,hp->shape_pose,grp_found?grp_frac:1.f,
                                                 &f,hn,pt)) {
                    grp_found=1;grp_frac=f;
                    memcpy(grp_n,hn,sizeof(grp_n));memcpy(grp_p,pt,sizeof(grp_p));
                }
            }
            if(grp_found&&(!best_found||grp_frac<best_frac)) {
                best_found=1;best_frac=grp_frac;
                memcpy(best_n,grp_n,sizeof(best_n));memcpy(best_p,grp_p,sizeof(best_p));
            }
            if(best_found&&(!hit.found||(double)best_frac<=hit.fraction)) {
                hit.found=1;hit.fraction=(double)best_frac;
                for(int a=0;a<3;++a){hit.normal[a]=(double)best_n[a];hit.point[a]=(double)best_p[a]-p->origin[a];}
                hit.face=0;
            }
        }
        if(!hit.found)continue;
        double *normal=hit.normal,a1=-dot(normal,de);if(a1<=0.)continue;
        double change[3];int equal=1;for(int a=0;a<3;++a){change[a]=hit.point[a]-p->point[a];if(normal[a]!=p->normal[a])equal=0;}
        if(equal&&fabs(dot(normal,change))<=1e-10) {
            double a0=-dot(normal,p->direction),reciprocal=(1/a0+1/a1)/2;
            double extent=crown_secant_value(dot(normal,p->axis),dot(normal,we),p->radius,p->width/2,p->shoulder,p->crown);
            double p0=a0*p->length;for(int a=0;a<3;++a)change[a]=we[a]-p->axis[a];double axis_change=dot(normal,change);
            for(int a=0;a<3;++a)change[a]=dt*v[a]+he[a]-p->hub[a];
            double p1=p0+dot(normal,change)-extent*axis_change,arm[3],moment[3];
            for(int a=0;a<3;++a)arm[a]=reciprocal*(ha[a]-extent*wa[a])+(p0+p1)/(2*a0*a1)*da[a];
            cross_regular(arm,normal,moment);
            for(int a=0;a<3;++a){g[a]=reciprocal*normal[a];g[a+3]=moment[a];}a1=1/reciprocal;
        } else {
            double arm[3],old_moment[3],new_moment[3],a0=-dot(p->normal,p->direction),terms[8],state[6];
            for(int a=0;a<3;++a)arm[a]=hit.point[a]-dt*v[a];
            cross_regular(p->point,p->normal,old_moment);cross_regular(arm,normal,new_moment);
            for(int a=0;a<3;++a){g[a]=(p->normal[a]/a0+normal[a]/a1)/2;
                g[a+3]=scale*(old_moment[a]/a0+new_moment[a]/a1)/2;state[a]=v[a];state[a+3]=omega[a];}
            for(int a=0;a<6;++a)terms[a]=state[a]*state[a];double squared=sum_values(terms,6);
            if(squared!=0.) {
                double difference=-p->radius+hit.fraction*(p->radius+p->reach)-p->length;
                if(hit.face) {
                    double support[3];if(!support_values(normal,p->axis,p->radius,p->width/2,p->shoulder,p->crown,support))return 0;
                    for(int a=0;a<3;++a){terms[a]=normal[a]*(p->hub[a]-hit.anchor[a]);terms[a+3]=-normal[a]*support[a];}
                    terms[6]=-hit.margin;terms[7]=dot(normal,p->direction)*p->length;double clearance=joint_fsum(terms,8);
                    double axis_length=sqrt(dot(p->axis,p->axis)),normal_length=sqrt(dot(normal,normal));
                    double extent=normal_length*crown_secant_value(dot(normal,p->axis)/(normal_length*axis_length),
                        dot(normal,we)/(normal_length*axis_length),p->radius,p->width/2,p->shoulder,p->crown);
                    double hr[3],dr[3],wr[3],transport[3];cross_regular(omega,ha,hr);cross_regular(omega,da,dr);cross_regular(omega,wa,wr);
                    for(int a=0;a<3;++a)transport[a]=v[a]+hr[a]+p->length*dr[a]-extent*wr[a]/axis_length;
                    double pair[2]={clearance,dt*dot(normal,transport)};difference=joint_fsum(pair,2)/-dot(normal,de);
                }
                for(int a=0;a<6;++a)terms[a]=g[a]*state[a];double correction=(difference/dt-sum_values(terms,6))/squared;
                for(int a=0;a<6;++a)g[a]=g[a]+correction*state[a];
            }
        }
        alignment[i]=a1;touching[i]=1.;
    }
    return 1;
}
static void joint_contact_begin(NativeSolveError *error){native_solve_error=error;}
static void joint_contact_end(void){native_solve_error=NULL;}
static JointContactApi joint_contact_api={joint_contact_evaluate,joint_contact_begin,joint_contact_end,joint_contact_queries_world_values};

static PyObject *joint_contact_state(PyObject *self,PyObject *args) {
    PyObject *capsule,*linear,*rotation;double dt,velocity[3],angular[3],gradients[24],alignment[4],touching[4];
    if(!PyArg_ParseTuple(args,"OOOd",&capsule,&linear,&rotation,&dt))return NULL;
    JointContacts *data=PyCapsule_GetPointer(capsule,JOINT_CONTACT_PACKET_NAME);
    if(!data||!vector(linear,velocity)||!vector(rotation,angular))return NULL;
    if(!joint_contact_evaluate(data,velocity,angular,dt,gradients,alignment,touching))return NULL;
    PyObject *g=PyTuple_New(4),*a=PyTuple_New(4),*t=PyTuple_New(4),*counts=PyTuple_New(4);
    if(!g||!a||!t||!counts)goto failed;
    for(int i=0;i<4;++i) {
        double *row=gradients+6*i;
        PyObject *gradient=Py_BuildValue("(dddddd)",row[0],row[1],row[2],row[3],row[4],row[5]);
        PyObject *value=touching[i]!=0.?PyFloat_FromDouble(alignment[i]):Py_NewRef(Py_None);
        PyObject *contact=PyBool_FromLong(touching[i]!=0.);
        PyObject *count=Py_BuildValue("(nn)",data->planes[i].candidate?data->planes[i].candidate->count:-1,
                                     data->planes[i].complete?data->planes[i].complete->count:0);
        if(!gradient||!value||!contact||!count){Py_XDECREF(gradient);Py_XDECREF(value);Py_XDECREF(contact);Py_XDECREF(count);goto failed;}
        PyTuple_SET_ITEM(g,i,gradient);PyTuple_SET_ITEM(a,i,value);PyTuple_SET_ITEM(t,i,contact);PyTuple_SET_ITEM(counts,i,count);
    }
    return Py_BuildValue("(NNNN)",g,a,t,counts);
failed:
    Py_XDECREF(g);Py_XDECREF(a);Py_XDECREF(t);Py_XDECREF(counts);return NULL;
}

static PyObject *joint_coordinates_probe(PyObject *self,PyObject *args) {
    PyObject *columns,*rhs;if(!PyArg_ParseTuple(args,"OO",&columns,&rhs))return NULL;
    Py_ssize_t count=PyTuple_Size(columns);if(count<1||count>3){PyErr_SetString(PyExc_ValueError,"单纯形须为一至三列");return NULL;}
    double matrix[3][3],input[3],values[3];int rank;
    for(int i=0;i<count;++i)if(!vector(PyTuple_GET_ITEM(columns,i),matrix[i]))return NULL;
    if(!vector(rhs,input))return NULL;WheelConvex shape={0};shape.coordinates=Py_None;
    if(!wheel_coordinates(&shape,matrix,(int)count,input,values,&rank))return NULL;
    PyObject *result=PyTuple_New(count);if(!result)return NULL;
    for(int i=0;i<count;++i){PyObject *value=PyFloat_FromDouble(values[i]);if(!value){Py_DECREF(result);return NULL;}PyTuple_SET_ITEM(result,i,value);}
    return Py_BuildValue("Ni",result,rank);
}

static PyObject *joint_surface_prepare(PyObject *self,PyObject *args) {
    PyObject *groups;if(!PyArg_ParseTuple(args,"O",&groups))return NULL;
    PyObject *surfaces=PyList_New(0);if(!surfaces)return NULL;
    Py_ssize_t count=PySequence_Size(groups);
    for(Py_ssize_t i=0;i<count;++i) {
        PyObject *group=PySequence_GetItem(groups,i);if(!group){Py_DECREF(surfaces);return NULL;}
        if(PyTuple_GET_ITEM(group,1)!=Py_True){PyErr_SetString(PyExc_ValueError,"当前原生阶段不接管唯一世界凸体扫掠");Py_DECREF(group);Py_DECREF(surfaces);return NULL;}
        PyObject *parts=PyTuple_GET_ITEM(group,2);
        for(Py_ssize_t j=0;j<PyTuple_GET_SIZE(parts);++j) {
            PyObject *part=PyTuple_GET_ITEM(parts,j);
            PyObject *row=PyTuple_Pack(8,PyTuple_GET_ITEM(group,0),PyTuple_GET_ITEM(part,0),PyTuple_GET_ITEM(part,1),
                PyTuple_GET_ITEM(part,3),PyTuple_GET_ITEM(part,4),PyTuple_GET_ITEM(part,5),PyTuple_GET_ITEM(part,6),PyTuple_GET_ITEM(part,2));
            if(!row||PyList_Append(surfaces,row)<0){Py_XDECREF(row);Py_DECREF(group);Py_DECREF(surfaces);return NULL;}Py_DECREF(row);
        }
        Py_DECREF(group);
    }
    PyObject *result=surface_packet_create(surfaces);Py_DECREF(surfaces);return result;
}
