#include "joint_contact_api.h"
typedef struct {
    int present;
    double hub[3],direction[3],normal[3],point[3],length;
    double axis[3],origin[3],low[3],high[3],radius,reach,width,shoulder,crown;
    SurfacePacket *surfaces;
    SurfacePacket *complete;
} JointPlane;
typedef struct { JointPlane planes[4]; double damping; PyObject *complete_owners; } JointContacts;

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

static void joint_contacts_free(PyObject *capsule) {
    JointContacts *data=PyCapsule_GetPointer(capsule,JOINT_CONTACT_PACKET_NAME);
    if(!data)return;
    for(int i=0;i<4;++i)if(data->planes[i].surfaces)surface_packet_free(data->planes[i].surfaces);
    Py_XDECREF(data->complete_owners);
    PyMem_Free(data);
}

static PyObject *joint_contact_prepare(PyObject *self,PyObject *args) {
    PyObject *contacts,*complete=Py_None;double damping;
    if(!PyArg_ParseTuple(args,"Od|O",&contacts,&damping,&complete))return NULL;
    if(PyTuple_Size(contacts)!=4){PyErr_SetString(PyExc_ValueError,"连续求解须为四轮接点");return NULL;}
    if(complete!=Py_None&&(!PyTuple_Check(complete)||PyTuple_GET_SIZE(complete)!=4)){
        PyErr_SetString(PyExc_ValueError,"完整几何须与四轮对应");return NULL;}
    JointContacts *data=PyMem_Calloc(1,sizeof(*data));if(!data)return PyErr_NoMemory();
    data->damping=damping;
    data->complete_owners=Py_NewRef(complete);
    for(int i=0;i<4;++i) {
        PyObject *contact=PyTuple_GET_ITEM(contacts,i);JointPlane *plane=&data->planes[i];
        if(contact==Py_None)continue;
        if(complete!=Py_None) {
            plane->complete=PyCapsule_GetPointer(PyTuple_GET_ITEM(complete,i),surface_packet_name);
            if(!plane->complete)goto failed;
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
    for(int i=0;i<4;++i)if(data->planes[i].surfaces)surface_packet_free(data->planes[i].surfaces);
    Py_XDECREF(data->complete_owners);
    PyMem_Free(data);return NULL;
}

static int joint_contact_evaluate(void *packet,const double *velocity,const double *angular,double dt,
                                 double *gradients,double *alignment,double *touching) {
    JointContacts *data=packet;double axis[3]={0.},angle=0.,scale=1.;
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
                selected=p->complete;break;
            }
        }
        SurfaceEntry hit={0};
        if(!joint_surface_values(selected,start,end,we,p->origin,p->radius,p->width,p->shoulder,p->crown,&hit))return 0;
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
static JointContactApi joint_contact_api={joint_contact_evaluate};

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
