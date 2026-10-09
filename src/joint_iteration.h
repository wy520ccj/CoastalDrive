#include "joint_contact_api.h"
#include "joint_iteration_helpers.h"

typedef struct {
    double key[6],gradients[24],alignment[4],touching[4];
} JointGeometryRecord;
typedef struct {
    int busy,sweep,shared_branch,shared_port,warm_branches[4],warm_modes[27][4],cache_count;
    WheelMap *map;SuspensionCoefficients *suspension;JointContactApi *api;void *contacts;
    double state[9],initial_velocity[3],velocity[3],port_values[4],forces[4][3];
    double previous[8],moment_x[12],moment_y[12],rolling[4],supported[4],loads[4];
    double hardware[20],law[28],parameters[12],normal[4],gradients[24],touching[4],alignment[4];
    double responses[36],mobility[16],road[4],active[3],bias_ports[2];
    double maximum,brake_error,normal_error,geometry_error;
    JointGeometryRecord geometry_cache[512];
} JointWork;

static void joint_workspace_free(PyObject *capsule) {
    PyMem_Free(PyCapsule_GetPointer(capsule,"CoastalDrive.joint_workspace.v1"));
}
static PyObject *joint_workspace(PyObject *self,PyObject *args) {
    JointWork *work=PyMem_Calloc(1,sizeof(*work));if(!work)return PyErr_NoMemory();
    PyObject *capsule=PyCapsule_New(work,"CoastalDrive.joint_workspace.v1",joint_workspace_free);
    if(!capsule)PyMem_Free(work);return capsule;
}
static void joint_cross(const double *a,const double *b,double *c) {
    c[0]=a[1]*b[2]-a[2]*b[1];c[1]=a[2]*b[0]-a[0]*b[2];c[2]=a[0]*b[1]-a[1]*b[0];
}
static int joint_geometry(JointWork *w,const double *velocity,const double *angular,
                          double *gradients,double *alignment,double *touching) {
    double key[6];memcpy(key,velocity,3*sizeof(double));memcpy(key+3,angular,3*sizeof(double));
    for(int i=0;i<w->cache_count;++i)if(memcmp(key,w->geometry_cache[i].key,sizeof(key))==0) {
        JointGeometryRecord *r=&w->geometry_cache[i];memcpy(gradients,r->gradients,24*sizeof(double));
        memcpy(alignment,r->alignment,4*sizeof(double));memcpy(touching,r->touching,4*sizeof(double));return 1;
    }
    if(!w->api->evaluate(w->contacts,velocity,angular,w->map->shared->dt,gradients,alignment,touching))return 0;
    if(w->cache_count<512) {
        JointGeometryRecord *r=&w->geometry_cache[w->cache_count++];memcpy(r->key,key,sizeof(key));
        memcpy(r->gradients,gradients,24*sizeof(double));memcpy(r->alignment,alignment,4*sizeof(double));memcpy(r->touching,touching,4*sizeof(double));
    }
    return 1;
}
static void joint_projection(JointWork *w) {
    const MassCoefficients *data=&w->map->shared->mass;double bare[24],mass=w->map->load.mass;
    for(int i=0;i<4;++i) {
        double source[9]={0.},terms[6];
        for(int a=0;a<3;++a){source[a]=w->gradients[6*i+a+3];bare[6*i+a]=w->gradients[6*i+a]/mass;}
        mass_response_values(data,source,w->responses+9*i);
        for(int a=0;a<3;++a){for(int b=0;b<3;++b)terms[b]=data->inverse[a*3+b]*w->gradients[6*i+b+3];bare[6*i+a+3]=compensated(terms,3);}
    }
    for(int i=0;i<4;++i)for(int j=0;j<4;++j){double terms[6];for(int a=0;a<6;++a)terms[a]=w->gradients[6*i+a]*bare[6*j+a];w->mobility[4*i+j]=compensated(terms,6);}
}
static int joint_normal(JointWork *w,const double *velocity,const double *angular,int precondition,double result[4]) {
    SuspensionCoefficients *data=w->suspension;double speed[4],terms[6],zero[16]={0.},end[4],raw[4],damping[4];
    const double *mobility=precondition?w->mobility:zero;
    for(int i=0;i<4;++i) {
        for(int a=0;a<6;++a)terms[a]=w->gradients[6*i+a]*(a<3?velocity[a]:angular[a-3]);double free=compensated(terms,6);
        for(int j=0;j<4;++j)terms[j]=mobility[4*i+j]*w->normal[j];speed[i]=free-data->dt*compensated(terms,4);
    }
    return suspension_contact_values(data->compression,speed,mobility,w->touching,data->stiffness,data->cd,data->ed,data->stops,
        data->travel,data->dt,data->geometry,end,result,raw,damping);
}
static void joint_load_parameters(JointWork *w) {
    for(int i=0;i<4;++i){const double *p=w->law+7*i;double load=w->loads[i],ratio=load/(p[1]*9.81/4);
        w->parameters[3*i]=load==0.?0.:p[0]*load*pow(ratio,p[2]-1);
        w->parameters[3*i+1]=p[3]*pow(ratio,p[4]);w->parameters[3*i+2]=p[5]*pow(ratio,p[6]);}
}
static void joint_normal_loads(JointWork *w) {
    for(int i=0;i<4;++i)w->loads[i]=w->supported[i]!=0.&&w->touching[i]!=0.&&w->normal[i]>0.?w->normal[i]/w->alignment[i]:0.;
    joint_load_parameters(w);
}
static void joint_load(JointWork *w,int exclude,double angular[9],double normal[9],double velocity[3]) {
    LoadCoefficients *data=&w->map->load;double terms[4];
    for(int a=0;a<9;++a){int count=0;for(int i=0;i<4;++i)if(i!=exclude)terms[count++]=w->forces[i][0]*data->responses[27*i+a]
        +w->forces[i][1]*data->responses[27*i+9+a]-w->forces[i][2]*data->responses[27*i+18+a];angular[a]=data->dt*compensated(terms,count);}
    for(int a=0;a<3;++a){int count=0;for(int i=0;i<4;++i)if(i!=exclude)terms[count++]=w->forces[i][0]*data->tangents[3*i+a]+w->forces[i][1]*data->axles[3*i+a];
        velocity[a]=w->initial_velocity[a]+data->dt/data->mass*compensated(terms,count);}
    for(int a=0;a<9;++a){for(int i=0;i<4;++i)terms[i]=w->normal[i]*w->responses[9*i+a];normal[a]=data->dt*compensated(terms,4);}
    for(int a=0;a<3;++a){for(int i=0;i<4;++i)terms[i]=w->normal[i]*w->gradients[6*i+a];velocity[a]=velocity[a]+data->dt/data->mass*compensated(terms,4);}
}
static int joint_shared(JointWork *w,const double guess[9]) {
    double state[11],angular[9],normal[9];memcpy(state,guess,9*sizeof(double));joint_load(w,-1,angular,normal,w->velocity);
    return joint_shared_values(w->map->shared,state,angular,normal,w->loads,w->supported,w->shared_branch,w->bias_ports,
        w->state,w->road,w->active,w->port_values,&w->shared_branch,&w->shared_port);
}
static int joint_wheel(JointWork *w,int i,const double gyro[3]) {
    JointWheelForce c={0};c.map=w->map;c.wheel=i;c.rolling=w->rolling[i]!=0.;c.hypot=Py_None;
    c.warm_branches=w->warm_branches;c.warm_modes=w->warm_modes;
    double angular[9],normal[9],force[2]={w->forces[i][0],w->forces[i][1]},brake;
    joint_load(w,i,angular,normal,c.velocity);SharedMap *data=w->map->shared;
    known_values(&data->mass,data->base,gyro,angular,normal,data->dt,data->rolling?w->road:NULL,c.base);
    memcpy(c.active,w->active,sizeof(c.active));memcpy(c.tangent,w->map->load.tangents+3*i,sizeof(c.tangent));
    memcpy(c.axle,w->map->load.axles+3*i,sizeof(c.axle));memcpy(c.moment_x,w->moment_x+3*i,sizeof(c.moment_x));
    memcpy(c.moment_y,w->moment_y+3*i,sizeof(c.moment_y));memcpy(c.previous,w->previous+2*i,sizeof(c.previous));
    memcpy(c.parameters,w->parameters+3*i,sizeof(c.parameters));memcpy(c.hardware,w->hardware+5*i,sizeof(c.hardware));c.radius=data->radii[i];
    int predict=w->sweep==0&&c.rolling&&w->loads[i]>0.;
    if(!joint_wheel_force_result(&c,.0001,force,predict,&brake))return 0;
    w->forces[i][0]=force[0];w->forces[i][1]=force[1];w->forces[i][2]=brake;return 1;
}
static int joint_contact_errors(JointWork *w,double *errors) {
    SharedMap *data=w->map->shared;w->maximum=0.;w->brake_error=0.;
    for(int i=0;i<4;++i){const double *p=w->parameters+3*i,*h=w->hardware+5*i;double speed[2],slip[2],target[2],deformation[2],rate[2],patch[2],kappa,alpha,terms[9];const char *mode;
        wheel_velocity_values(w->state,w->velocity,i+5,w->map->load.tangents+3*i,w->map->load.axles+3*i,w->moment_x+3*i,w->moment_y+3*i,data->radii[i],speed,slip);
        double denominator=fabs(speed[0])>h[0]?fabs(speed[0]):h[0];
        if(!tire_contact_values(w->forces[i],w->previous+2*i,slip,denominator,w->rolling[i]!=0.,p[0],p[1],p[2],data->dt,h[1],h[2],h[3],h[4],Py_None,target,deformation,rate,patch,&kappa,&alpha,&mode))return 0;
        double ex=w->forces[i][0]-target[0],ey=w->forces[i][1]-target[1],error=hypot_two(ex,ey);
        if(errors){errors[2*i]=ex;errors[2*i+1]=ey;}if(error>w->maximum)w->maximum=error;
        for(int a=0;a<9;++a)terms[a]=w->map->brake_gradients[i][a]*w->state[a];double brake_speed=compensated(terms,9);
        for(int a=0;a<9;++a)terms[a]=w->map->brake_gradients[i][a]*w->map->load.responses[27*i+18+a];double response=compensated(terms,9);
        double brake=w->forces[i][2],demand=brake+brake_speed/(data->dt*response),capacity=w->map->brakes[i];
        demand=demand<capacity?demand:capacity;demand=demand>-capacity?demand:-capacity;error=fabs(brake-demand);if(error>w->brake_error)w->brake_error=error;
    }
    return 1;
}
static int joint_contact_residual(JointWork *w,const double values[8],const double brakes[4],const double guess[9],double errors[8]) {
    for(int i=0;i<4;++i){w->forces[i][0]=values[2*i];w->forces[i][1]=values[2*i+1];w->forces[i][2]=brakes[i];}
    if(!joint_shared(w,guess)||!joint_brake_values(w->map,w->state,w->forces,w->shared_branch,w->shared_port)||!joint_shared(w,w->state))return 0;
    return joint_contact_errors(w,errors);
}
static int joint_correct_contacts(JointWork *w) {
    double original_maximum=w->maximum,original_brake_error=w->brake_error;
    double original[12],values[8],brakes[4],guess[9],saved_velocity[3],errors[8],columns[8][8],rows[8][9],largest=0.;
    memcpy(original,w->forces,sizeof(original));memcpy(guess,w->state,sizeof(guess));memcpy(saved_velocity,w->velocity,sizeof(saved_velocity));
    for(int i=0;i<4;++i){values[2*i]=w->forces[i][0];values[2*i+1]=w->forces[i][1];brakes[i]=w->forces[i][2];}
    if(!joint_contact_residual(w,values,brakes,guess,errors))return 0;
    for(int j=0;j<8;++j){double plus[8],minus[8],high[8],low[8];memcpy(plus,values,sizeof(values));memcpy(minus,values,sizeof(values));plus[j]+=.01;minus[j]-=.01;
        if(!joint_contact_residual(w,plus,brakes,guess,high)||!joint_contact_residual(w,minus,brakes,guess,low))return 0;
        for(int i=0;i<8;++i)columns[j][i]=(high[i]-low[i])/.02;}
    for(int i=0;i<8;++i){for(int j=0;j<8;++j){rows[i][j]=columns[j][i];if(fabs(rows[i][j])>largest)largest=fabs(rows[i][j]);}rows[i][8]=-errors[i];}
    int row=0,pivots[8];double rounding=32*(nextafter(largest,INFINITY)-largest);
    for(int col=0;col<8;++col){int pivot=row;for(int i=row+1;i<8;++i)if(fabs(rows[i][col])>fabs(rows[pivot][col]))pivot=i;
        if(fabs(rows[pivot][col])<=rounding)continue;
        for(int j=0;j<9;++j){double swap=rows[row][j];rows[row][j]=rows[pivot][j];rows[pivot][j]=swap;}
        double scale=rows[row][col];for(int j=0;j<9;++j)rows[row][j]/=scale;
        for(int i=0;i<8;++i)if(i!=row){double factor=rows[i][col];for(int j=0;j<9;++j)rows[i][j]-=factor*rows[row][j];}
        pivots[row]=col;if(++row==8)break;}
    double delta[8]={0.},before=0.;for(int i=0;i<row;++i)delta[pivots[i]]=rows[i][8];
    for(int i=0;i<4;++i){double e=hypot_two(errors[2*i],errors[2*i+1]);if(e>before)before=e;}
    int accepted=0;
    for(int attempt=0;attempt<8;++attempt){double candidate[8],after[8];for(int i=0;i<8;++i)candidate[i]=values[i]+ldexp(1.,-attempt)*delta[i];
        if(!joint_contact_residual(w,candidate,brakes,guess,after))return 0;
        double maximum=0.;for(int i=0;i<4;++i){double e=hypot_two(after[2*i],after[2*i+1]);if(e>maximum)maximum=e;}
        if(maximum<before){accepted=1;break;}}
    if(!accepted)memcpy(w->forces,original,sizeof(original));
    memcpy(w->state,guess,sizeof(guess));memcpy(w->velocity,saved_velocity,sizeof(saved_velocity));
    w->maximum=original_maximum;w->brake_error=original_brake_error;return 1;
}
static int joint_suspension_residual(JointWork *w,const double values[6],const double guess[9],double errors[6]) {
    double state[9];memcpy(state,guess,9*sizeof(double));memcpy(state,values+3,3*sizeof(double));
    if(!joint_geometry(w,values,values+3,w->gradients,w->alignment,w->touching))return 0;
    joint_projection(w);if(!joint_normal(w,values,values+3,0,w->normal)||!joint_shared(w,state))return 0;
    for(int a=0;a<6;++a)errors[a]=values[a]-(a<3?w->velocity[a]:w->state[a-3]);return 1;
}
static int joint_correct_suspension(JointWork *w) {
    double saved_gradients[24],saved_alignment[4],saved_touching[4],saved_normal[4],guess[9],saved_velocity[3],values[6],errors[6],columns[6][6];
    memcpy(saved_gradients,w->gradients,sizeof(saved_gradients));memcpy(saved_alignment,w->alignment,sizeof(saved_alignment));
    memcpy(saved_touching,w->touching,sizeof(saved_touching));memcpy(saved_normal,w->normal,sizeof(saved_normal));
    memcpy(guess,w->state,sizeof(guess));memcpy(saved_velocity,w->velocity,sizeof(saved_velocity));memcpy(values,w->velocity,3*sizeof(double));memcpy(values+3,w->state,3*sizeof(double));
    if(!joint_suspension_residual(w,values,guess,errors))return 0;
    for(int j=0;j<6;++j){double plus[6],minus[6],high[6],low[6];memcpy(plus,values,sizeof(values));memcpy(minus,values,sizeof(values));plus[j]+=.0001;minus[j]-=.0001;
        if(!joint_suspension_residual(w,plus,guess,high)||!joint_suspension_residual(w,minus,guess,low))return 0;
        for(int i=0;i<6;++i)columns[j][i]=(high[i]-low[i])/.0002;}
    double matrix[36],rhs[6],lu[36],delta[6],residual[6],correction[6],terms[7],partials[7],before=0.;Py_ssize_t order[6];
    for(int i=0;i<6;++i){rhs[i]=-errors[i];if(fabs(errors[i])>before)before=fabs(errors[i]);for(int j=0;j<6;++j)matrix[6*i+j]=columns[j][i];}
    if(!lu_values(matrix,rhs,6,lu,order,delta,residual,correction,terms,partials))return 0;
    int accepted=0;
    for(int attempt=0;attempt<8;++attempt){double candidate[6],after[6],maximum=0.;for(int i=0;i<6;++i)candidate[i]=values[i]+ldexp(1.,-attempt)*delta[i];
        if(!joint_suspension_residual(w,candidate,guess,after))return 0;for(int i=0;i<6;++i)if(fabs(after[i])>maximum)maximum=fabs(after[i]);
        if(maximum<before){joint_normal_loads(w);accepted=1;break;}}
    if(!accepted){memcpy(w->gradients,saved_gradients,sizeof(saved_gradients));memcpy(w->alignment,saved_alignment,sizeof(saved_alignment));
        memcpy(w->touching,saved_touching,sizeof(saved_touching));memcpy(w->normal,saved_normal,sizeof(saved_normal));joint_projection(w);}
    memcpy(w->state,guess,sizeof(guess));memcpy(w->velocity,saved_velocity,sizeof(saved_velocity));return 1;
}

static int joint_iterate(JointWork *w) {
    joint_projection(w);joint_load_parameters(w);
    for(w->sweep=0;w->sweep<20;++w->sweep) {
        if(!joint_shared(w,w->state)||!joint_geometry(w,w->velocity,w->state,w->gradients,w->alignment,w->touching))return 0;
        joint_projection(w);if(!joint_normal(w,w->velocity,w->state,1,w->normal))return 0;
        joint_normal_loads(w);if(!joint_shared(w,w->state))return 0;
        double spin[3],gyro[3];rotor_spin_values(&w->map->shared->spin,w->state,spin);joint_cross(spin,w->state,gyro);
        for(int j=0;j<4;++j){int i=w->sweep%2?3-j:j;if(!joint_wheel(w,i,gyro))return 0;}
        if(!joint_shared(w,w->state)||!joint_brake_values(w->map,w->state,w->forces,w->shared_branch,w->shared_port)||!joint_shared(w,w->state))return 0;
        if(!joint_normal(w,w->velocity,w->state,0,w->normal))return 0;joint_normal_loads(w);if(!joint_shared(w,w->state)||!joint_contact_errors(w,NULL))return 0;
        double target_forces[4],target_gradients[24],target_alignment[4],target_touching[4],terms[4];
        if(!joint_normal(w,w->velocity,w->state,0,target_forces)||!joint_geometry(w,w->velocity,w->state,target_gradients,target_alignment,target_touching))return 0;
        w->normal_error=0.;w->geometry_error=0.;
        for(int i=0;i<4;++i){double error=fabs(w->normal[i]-target_forces[i]);if(error>w->normal_error)w->normal_error=error;}
        for(int a=0;a<6;++a){for(int i=0;i<4;++i)terms[i]=w->normal[i]*(target_gradients[6*i+a]-w->gradients[6*i+a]);
            double error=fabs(compensated(terms,4));if(error>w->geometry_error)w->geometry_error=error;}
        w->geometry_error*=w->map->shared->dt;
        if(w->maximum<.001&&w->brake_error<1e-9&&w->normal_error<1e-10&&w->geometry_error<1e-12)return 1;
        if(w->sweep>=8&&(w->maximum>=.001||w->geometry_error>=1e-12)&&!joint_correct_contacts(w))return 0;
        if(w->sweep>=8&&w->maximum<.001&&(w->normal_error>=1e-10||w->geometry_error>=1e-12)&&!joint_correct_suspension(w))return 0;
    }
    char message[256];PyOS_snprintf(message,sizeof(message),"连续原生共同求解超过20轮：力%.9g，制动%.9g，法向%.9g，几何%.9g",w->maximum,w->brake_error,w->normal_error,w->geometry_error);
    PyErr_SetString(PyExc_ArithmeticError,message);return 0;
}
static PyObject *joint_vector_object(const double *data,int n) {
    PyObject *result=PyTuple_New(n);if(!result)return NULL;
    for(int i=0;i<n;++i){PyObject *value=PyFloat_FromDouble(data[i]);if(!value){Py_DECREF(result);return NULL;}PyTuple_SET_ITEM(result,i,value);}return result;
}
static PyObject *joint_matrix_object(const double *data,int rows,int columns) {
    PyObject *result=PyTuple_New(rows);if(!result)return NULL;
    for(int i=0;i<rows;++i){PyObject *row=joint_vector_object(data+i*columns,columns);if(!row){Py_DECREF(result);return NULL;}PyTuple_SET_ITEM(result,i,row);}return result;
}
static PyObject *joint_solve(PyObject *self,PyObject *args) {
    PyObject *workspace,*wheel,*suspension,*contacts,*input;
    if(!PyArg_ParseTuple(args,"OOOOO",&workspace,&wheel,&suspension,&contacts,&input))return NULL;
    JointWork *w=PyCapsule_GetPointer(workspace,"CoastalDrive.joint_workspace.v1");if(!w)return NULL;
    if(w->busy){PyErr_SetString(PyExc_RuntimeError,"同一原生共同求解工作区被重入");return NULL;}
    w->map=PyCapsule_GetPointer(wheel,wheel_map_name);w->suspension=PyCapsule_GetPointer(suspension,suspension_coefficients_name);
    w->contacts=PyCapsule_GetPointer(contacts,JOINT_CONTACT_PACKET_NAME);if(!w->map||!w->suspension||!w->contacts)return NULL;
    PyObject *module=PyImport_ImportModule("wheel_contact_kernels");if(!module)return NULL;
    PyObject *api=PyObject_GetAttrString(module,"_joint_contact_api");Py_DECREF(module);if(!api)return NULL;
    w->api=PyCapsule_GetPointer(api,JOINT_CONTACT_API_NAME);Py_DECREF(api);if(!w->api||!tuple_fields(input,14))return NULL;
    if(!vector(PyTuple_GET_ITEM(input,0),w->state,9)||!vector(PyTuple_GET_ITEM(input,1),w->initial_velocity,3)
        ||!matrix_values(PyTuple_GET_ITEM(input,2),&w->forces[0][0],4,3)||!matrix_values(PyTuple_GET_ITEM(input,3),w->previous,4,2)
        ||!matrix_values(PyTuple_GET_ITEM(input,4),w->moment_x,4,3)||!matrix_values(PyTuple_GET_ITEM(input,5),w->moment_y,4,3)
        ||!vector(PyTuple_GET_ITEM(input,6),w->rolling,4)||!vector(PyTuple_GET_ITEM(input,7),w->supported,4)
        ||!vector(PyTuple_GET_ITEM(input,8),w->loads,4)||!matrix_values(PyTuple_GET_ITEM(input,9),w->hardware,4,5)
        ||!matrix_values(PyTuple_GET_ITEM(input,10),w->law,4,7)||!matrix_values(PyTuple_GET_ITEM(input,11),w->gradients,4,6)
        ||!vector(PyTuple_GET_ITEM(input,12),w->touching,4)||!vector(PyTuple_GET_ITEM(input,13),w->alignment,4))return NULL;
    memset(w->normal,0,sizeof(w->normal));memset(w->road,0,sizeof(w->road));memset(w->bias_ports,0,sizeof(w->bias_ports));memset(w->warm_branches,0,sizeof(w->warm_branches));
    for(int i=0;i<27;++i)for(int j=0;j<4;++j)w->warm_modes[i][j]=-1;
    w->cache_count=0;w->shared_branch=0;w->shared_port=-1;w->busy=1;
    int success=joint_iterate(w);w->busy=0;if(!success)return NULL;
    PyObject *result=PyTuple_New(23);if(!result)return NULL;
    PyTuple_SET_ITEM(result,0,joint_vector_object(w->state,9));PyTuple_SET_ITEM(result,1,joint_vector_object(w->velocity,3));
    PyTuple_SET_ITEM(result,2,PyFloat_FromDouble(w->port_values[0]));PyTuple_SET_ITEM(result,3,PyFloat_FromDouble(w->port_values[2]));PyTuple_SET_ITEM(result,4,PyFloat_FromDouble(w->port_values[1]));
    PyTuple_SET_ITEM(result,5,joint_matrix_object(&w->forces[0][0],4,3));
    PyObject *modes=PyTuple_New(4),*alignment=PyTuple_New(4),*touching=PyTuple_New(4);
    if(!modes||!alignment||!touching){Py_XDECREF(modes);Py_XDECREF(alignment);Py_XDECREF(touching);Py_DECREF(result);return NULL;}
    for(int i=0;i<4;++i){PyTuple_SET_ITEM(modes,i,PyUnicode_FromString(w->loads[i]>0.?"magic-formula":"airborne"));
        PyTuple_SET_ITEM(alignment,i,w->touching[i]!=0.?PyFloat_FromDouble(w->alignment[i]):Py_NewRef(Py_None));PyTuple_SET_ITEM(touching,i,PyBool_FromLong(w->touching[i]!=0.));}
    PyTuple_SET_ITEM(result,6,modes);PyTuple_SET_ITEM(result,7,joint_vector_object(w->normal,4));PyTuple_SET_ITEM(result,8,joint_matrix_object(w->gradients,4,6));
    PyTuple_SET_ITEM(result,9,alignment);PyTuple_SET_ITEM(result,10,touching);PyTuple_SET_ITEM(result,11,joint_vector_object(w->loads,4));PyTuple_SET_ITEM(result,12,joint_matrix_object(w->parameters,4,3));
    PyTuple_SET_ITEM(result,13,PyLong_FromLong(w->shared_branch));PyTuple_SET_ITEM(result,14,PyLong_FromLong(w->shared_port));PyTuple_SET_ITEM(result,15,joint_vector_object(w->road,4));
    PyTuple_SET_ITEM(result,16,joint_vector_object(w->active,3));PyTuple_SET_ITEM(result,17,joint_vector_object(w->bias_ports,2));PyTuple_SET_ITEM(result,18,PyLong_FromLong(w->sweep+1));
    PyTuple_SET_ITEM(result,19,PyFloat_FromDouble(w->normal_error));PyTuple_SET_ITEM(result,20,PyFloat_FromDouble(w->geometry_error));PyTuple_SET_ITEM(result,21,PyFloat_FromDouble(w->maximum));PyTuple_SET_ITEM(result,22,PyFloat_FromDouble(w->brake_error));
    for(int i=0;i<23;++i)if(!PyTuple_GET_ITEM(result,i)){Py_DECREF(result);return NULL;}
    if(PyErr_Occurred()){Py_DECREF(result);return NULL;}
    w->map=NULL;w->suspension=NULL;w->contacts=NULL;return result;
}
