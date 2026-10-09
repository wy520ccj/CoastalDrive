
/* 当前线程的机械准备与共同迭代共用原类型；每次输入刷新实际系数。 */
static PyObject *joint_mechanical_workspace(PyObject *self,PyObject *args) {
    SharedMap *shared=PyMem_Calloc(1,sizeof(*shared));
    if(!shared)return PyErr_NoMemory();
    PyObject *shared_owner=PyCapsule_New(shared,shared_map_name,release_shared_map);
    if(!shared_owner){PyMem_Free(shared);return NULL;}
    WheelMap *wheel=PyMem_Calloc(1,sizeof(*wheel)+108*sizeof(WheelBranch));
    if(!wheel){Py_DECREF(shared_owner);return PyErr_NoMemory();}
    wheel->shared=shared;wheel->shared_owner=Py_NewRef(shared_owner);
    PyObject *wheel_owner=PyCapsule_New(wheel,wheel_map_name,release_wheel_map);
    if(!wheel_owner){Py_DECREF(shared_owner);Py_DECREF(wheel->shared_owner);PyMem_Free(wheel);return NULL;}
    return Py_BuildValue("NN",shared_owner,wheel_owner);
}

static double joint_mechanical_dot(const double *a,const double *b) {
    double terms[9];for(int i=0;i<9;++i)terms[i]=a[i]*b[i];return compensated(terms,9);
}
static int joint_plan_inverse(double rows[3][3],double result[3][3]) {
    double cofactors[3][3],terms[3];
    for(int i=0;i<3;++i){int a=(i+1)%3,b=(i+2)%3;
        cofactors[i][0]=rows[a][1]*rows[b][2]-rows[a][2]*rows[b][1];
        cofactors[i][1]=rows[a][2]*rows[b][0]-rows[a][0]*rows[b][2];
        cofactors[i][2]=rows[a][0]*rows[b][1]-rows[a][1]*rows[b][0];}
    for(int j=0;j<3;++j)terms[j]=rows[0][j]*cofactors[0][j];double determinant=compensated(terms,3);
    if(determinant==0.){PyErr_SetString(PyExc_ZeroDivisionError,"端口约束矩阵奇异");return 0;}
    for(int k=0;k<3;++k)for(int i=0;i<3;++i){for(int j=0;j<3;++j)terms[j]=cofactors[j][i]*(double)(j==k);
        result[k][i]=compensated(terms,3)/determinant;}
    return 1;
}
static int joint_mechanical_plans(SharedBranch *branch,double capacity,double brake,double efficiency) {
    const int ports[3]={0,2,3},modes[3]={0,1,-1},motions[3]={1,-1,0};
    double reduced[3][3],gear[3],cached_rows[45][3][3],cached_columns[45][3][3];int count=0;
    if(branch->port_response[1][1]==0.||efficiency==0.){
        PyErr_SetString(PyExc_ZeroDivisionError,"端口响应或效率为零");return 0;}
    for(int j=0;j<3;++j){gear[j]=branch->port_response[1][ports[j]]/branch->port_response[1][1];
        for(int i=0;i<3;++i)reduced[i][j]=branch->port_response[ports[i]][ports[j]]
            -branch->port_response[ports[i]][1]*branch->port_response[1][ports[j]]/branch->port_response[1][1];}
    branch->plan_count=0;
    for(int cm=capacity!=0.?0:1;cm<3;++cm)for(int mi=0;mi<3;++mi)
        for(int bm=brake!=0.?0:1;bm<3;++bm)for(int si=0;si<(motions[mi]!=0?2:1);++si){
            SharedPortPlan *plan=&branch->plans[branch->plan_count++];
            plan->modes[0]=modes[cm];plan->modes[1]=motions[mi];plan->modes[2]=modes[bm];
            plan->sign=motions[mi]!=0?(si==0?1:-1):0;
            plan->slope=motions[mi]*plan->sign>0?1-efficiency:1-1/efficiency;
            double rows[3][3];
            for(int j=0;j<3;++j){rows[0][j]=modes[cm]==0?reduced[0][j]:(double)(j==0);
                rows[1][j]=motions[mi]==0?reduced[1][j]:plan->slope*gear[j]+(double)(j==1);
                rows[2][j]=modes[bm]==0?reduced[2][j]:(double)(j==2);}
            int found=0;
            for(;found<count;++found){int equal=1;for(int i=0;i<3;++i)for(int j=0;j<3;++j)
                    if(rows[i][j]!=cached_rows[found][i][j])equal=0;if(equal)break;}
            if(found==count){if(!joint_plan_inverse(rows,cached_columns[count]))return 0;
                memcpy(cached_rows[count],rows,sizeof(rows));++count;}
            memcpy(plan->columns,cached_columns[found],sizeof(plan->columns));
        }
    return 1;
}

static PyObject *joint_mechanical_prepare(PyObject *self,PyObject *args) {
    PyObject *workspace,*mass_object,*spin_object,*base,*load_object,*ports,*differential,*damping,*limits,*responses,*rolling,*bias,*brake_gradients,*brakes;
    double dt,capacity,efficiency,synchronizer;int hard;
    if(!PyArg_ParseTuple(args,"OOOOOOOOOOddddpOOOO",&workspace,&mass_object,&spin_object,&base,&load_object,
        &ports,&differential,&damping,&limits,&responses,&dt,&capacity,&efficiency,&synchronizer,&hard,&rolling,&bias,&brake_gradients,&brakes))return NULL;
    if(!hard){PyErr_SetString(PyExc_ValueError,"此准备阶段使用实际已挂挡四端口");return NULL;}
    if(!tuple_fields(workspace,2))return NULL;
    SharedMap *data=PyCapsule_GetPointer(PyTuple_GET_ITEM(workspace,0),shared_map_name);
    WheelMap *wheel=PyCapsule_GetPointer(PyTuple_GET_ITEM(workspace,1),wheel_map_name);
    MassCoefficients *mass=PyCapsule_GetPointer(mass_object,mass_coefficients_name);
    RotorCoefficients *spin=PyCapsule_GetPointer(spin_object,rotor_coefficients_name);
    if(!data||!wheel||!mass||!spin)return NULL;
    if(mass->dimensions!=9||spin->dimensions!=9){PyErr_SetString(PyExc_ValueError,"机械准备须为实体输入轴九维机制");return NULL;}
    memset(data,0,offsetof(SharedMap,branches));
    data->mass=*mass; data->spin=*spin; data->dt=dt; data->capacity=capacity;
    for (int i=0;i<27;++i) data->port_seeds[i]=-1;
    for (int j=0; j<9; ++j) {
        double unit[9]={0.}; unit[j]=1.;
        rotor_spin_values(spin,unit,data->spin_columns[j]);
    }
    data->efficiency=efficiency; data->synchronizer=synchronizer; data->hard=hard;
    if (!vector(base,data->base,9) || !matrix_values(ports,&data->ports[0][0],hard ? 4 : 3,9)
        || !matrix_values(differential,&data->differential[0][0],3,9)
        || !vector(damping,data->damping,3) || !vector(limits,data->limits,3)
        || !tuple_fields(rolling,3) || !vector(PyTuple_GET_ITEM(rolling,0),data->radii,4)
        || !vector(PyTuple_GET_ITEM(rolling,1),data->rolling_coefficients,4)
        || !tuple_fields(bias,7)) goto failed;
    data->transition=PyFloat_AsDouble(PyTuple_GET_ITEM(rolling,2));
    data->ratio=PyFloat_AsDouble(PyTuple_GET_ITEM(bias,0));
    data->share=PyFloat_AsDouble(PyTuple_GET_ITEM(bias,1));
    data->final_drive=PyFloat_AsDouble(PyTuple_GET_ITEM(bias,2));
    if (PyErr_Occurred() || !vector(PyTuple_GET_ITEM(bias,3),data->biases,2)) goto failed;
    data->bias=data->biases[0]>1. || data->biases[1]>1.;
    if (data->bias && !matrix_values(responses,&data->differential_responses[0][0],3,9)) goto failed;
    PyObject *old=PyTuple_GET_ITEM(bias,6);
    if (!PyTuple_Check(old)) { PyErr_SetString(PyExc_ValueError,"实体轴初始速度须为元组"); goto failed; }
    data->downstream=PyTuple_GET_SIZE(old)!=0;
    if (data->downstream && (!vector(PyTuple_GET_ITEM(bias,4),data->inertias,3)
        || !matrix_values(PyTuple_GET_ITEM(bias,5),&data->down_gradients[0][0],3,9)
        || !vector(old,data->old_omega,3))) goto failed;
    for (int i=0; i<3; ++i) if (data->damping[i]!=0. && data->limits[i]!=0.) data->limited=1;
    for (int i=0; i<4; ++i) if (data->rolling_coefficients[i]!=0.) data->rolling=1;

    if(!matrix_values(brake_gradients,&wheel->brake_gradients[0][0],4,9)||!vector(brakes,wheel->brakes,4))goto failed;
    double longitudinal[4][9],lateral[4][9];
    if(!tuple_fields(load_object,5)||!matrix_values(PyTuple_GET_ITEM(load_object,0),&longitudinal[0][0],4,9)
        ||!matrix_values(PyTuple_GET_ITEM(load_object,1),&lateral[0][0],4,9)
        ||!matrix_values(PyTuple_GET_ITEM(load_object,2),wheel->load.tangents,4,3)
        ||!matrix_values(PyTuple_GET_ITEM(load_object,3),wheel->load.axles,4,3))goto failed;
    wheel->load.mass=PyFloat_AsDouble(PyTuple_GET_ITEM(load_object,4));if(PyErr_Occurred())goto failed;
    wheel->load.dt=dt;wheel->load.dimensions=9;
    for(int i=0;i<4;++i){mass_response_values(mass,longitudinal[i],wheel->load.responses+27*i);
        mass_response_values(mass,lateral[i],wheel->load.responses+27*i+9);
        mass_response_values(mass,wheel->brake_gradients[i],wheel->load.responses+27*i+18);}
    const LoadCoefficients *load=&wheel->load;
    double differential_response[3][9],port_response[3][9];
    for(int i=0;i<3;++i){mass_response_values(mass,data->differential[i],differential_response[i]);
        mass_response_values(mass,data->ports[i],port_response[i]);}
    const int modes[3]={0,1,-1};int counts[3];
    for(int i=0;i<3;++i)counts[i]=data->damping[i]!=0.&&data->limits[i]!=0.?3:1;
    data->branch_count=0;
    for(int x=0;x<counts[0];++x)for(int y=0;y<counts[1];++y)for(int z=0;z<counts[2];++z){
        int index=data->branch_count++;SharedBranch *branch=&data->branches[index];memset(branch,0,sizeof(*branch));
        branch->modes[0]=modes[x];branch->modes[1]=modes[y];branch->modes[2]=modes[z];
        for(int i=0;i<3;++i){if(data->damping[i]==0.||data->limits[i]==0.)continue;
            if(branch->modes[i]!=0.){for(int a=0;a<9;++a)branch->offset[a]=branch->offset[a]-dt*branch->modes[i]*data->limits[i]*differential_response[i][a];}
            else {int p=branch->projection_count;memcpy(branch->gradients[p],data->differential[i],9*sizeof(double));
                memcpy(branch->responses[p],differential_response[i],9*sizeof(double));shared_projection(branch,branch->responses[p]);
                branch->factors[p]=dt*data->damping[i]/(1+dt*data->damping[i]*joint_mechanical_dot(data->differential[i],branch->responses[p]));
                ++branch->projection_count;}}
        shared_projection(branch,branch->offset);
        memcpy(branch->mc,port_response[0],9*sizeof(double));shared_projection(branch,branch->mc);
        memcpy(branch->mg,port_response[1],9*sizeof(double));shared_projection(branch,branch->mg);
        memcpy(branch->ml,port_response[2],9*sizeof(double));shared_projection(branch,branch->ml);
        for(int i=0;i<4;++i){WheelBranch *local=&wheel->local[4*index+i];memset(local,0,sizeof(*local));
            double projected[3][9];for(int j=0;j<3;++j){memcpy(projected[j],load->responses+27*i+9*j,9*sizeof(double));shared_projection(branch,projected[j]);}
            memcpy(local->force_responses,projected,18*sizeof(double));memcpy(local->ports.mc,projected[2],9*sizeof(double));
            const double *g[4]={data->ports[0],data->ports[1],data->ports[2],wheel->brake_gradients[i]};
            const double *r[4]={branch->mc,branch->mg,branch->ml,projected[2]};
            for(int a=0;a<4;++a)for(int b=0;b<4;++b)local->ports.port_response[a][b]=joint_mechanical_dot(g[a],r[b]);
            if(!joint_mechanical_plans(&local->ports,capacity,wheel->brakes[i],efficiency))goto failed;
            if(i==0){memcpy(branch->port_response,local->ports.port_response,sizeof(branch->port_response));
                if(!joint_mechanical_plans(branch,capacity,0.,efficiency))goto failed;}}
    }
    return Py_NewRef(workspace);
failed:
    return NULL;
}

static PyObject *joint_differential_torques(PyObject *self,PyObject *args) {
    PyObject *shared_object,*input,*limits;int index;
    if(!PyArg_ParseTuple(args,"OOiO",&shared_object,&input,&index,&limits))return NULL;
    SharedMap *shared=PyCapsule_GetPointer(shared_object,shared_map_name);if(!shared)return NULL;
    double state[9],active[3],torques[3];if(!vector(input,state,9)||!vector(limits,active,3))return NULL;
    if(index<0||index>=shared->branch_count){PyErr_SetString(PyExc_ValueError,"实际限滑分区越界");return NULL;}
    if(!shared_branch_feasible(shared,&shared->branches[index],state,active))Py_RETURN_NONE;
    for(int i=0;i<3;++i){double mode=shared->branches[index].modes[i];
        torques[i]=shared->damping[i]!=0.&&active[i]!=0.?(mode!=0.?mode*active[i]:shared->damping[i]*joint_mechanical_dot(shared->differential[i],state)):0.;}
    return Py_BuildValue("(ddd)",torques[0],torques[1],torques[2]);
}
