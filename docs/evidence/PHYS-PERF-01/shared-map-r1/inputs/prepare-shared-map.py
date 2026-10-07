from pathlib import Path
block=r'''
/* 当前共同求解的固定机械分区；仅含数值，不持有车辆或物理世界。 */
typedef struct {
    double modes[3],sign,slope,columns[3][3];
} SharedPortPlan;
typedef struct {
    int projection_count,plan_count;
    double gradients[3][9],responses[3][9],factors[3],offset[9],modes[3];
    double mc[9],ml[9],mg[9],port_response[4][4];
    SharedPortPlan plans[45];
} SharedBranch;
typedef struct {
    MassCoefficients mass;
    RotorCoefficients spin;
    int hard,limited,bias,rolling,downstream,branch_count;
    double base[9],dt,capacity,efficiency,synchronizer;
    double ports[4][9],differential[3][9],damping[3],limits[3];
    double differential_responses[3][9],radii[4],rolling_coefficients[4],transition;
    double ratio,share,final_drive,biases[2],inertias[3],down_gradients[3][9],old_omega[3];
    SharedBranch branches[27];
} SharedMap;
static const char *shared_map_name="CoastalDrive.shared_map";
static void release_shared_map(PyObject *object) {
    PyMem_Free(PyCapsule_GetPointer(object,shared_map_name));
}
static int tuple_fields(PyObject *object,Py_ssize_t count) {
    if (!PyTuple_Check(object) || PyTuple_GET_SIZE(object)!=count) {
        PyErr_SetString(PyExc_ValueError,"共同机械数值结构不一致"); return 0;
    }
    return 1;
}
static PyObject *shared_map_coefficients(PyObject *self,PyObject *args,PyObject *kwargs) {
    PyObject *mass_object,*spin_object,*base,*branches,*ports,*differential,*damping,*limits,*responses,*rolling,*bias;
    double dt,capacity,efficiency,synchronizer;
    int hard;
    static char *names[]={"mass_coefficients","rotor_coefficients","free_base","branches","port_gradients",
        "differential_gradients","damping","limits","differential_responses","dt","capacity","efficiency",
        "synchronizer_capacity","hard_gear","rolling","bias",NULL};
    if (!PyArg_ParseTupleAndKeywords(args,kwargs,"OOOOOOOOOddddpOO",names,&mass_object,&spin_object,&base,
        &branches,&ports,&differential,&damping,&limits,&responses,&dt,&capacity,&efficiency,&synchronizer,&hard,
        &rolling,&bias)) return NULL;
    MassCoefficients *mass=PyCapsule_GetPointer(mass_object,mass_coefficients_name);
    RotorCoefficients *spin=PyCapsule_GetPointer(spin_object,rotor_coefficients_name);
    if (!mass || !spin) return NULL;
    if (mass->dimensions!=9 || spin->dimensions!=9) {
        PyErr_SetString(PyExc_ValueError,"共同分区映射须为实体输入轴九维机制"); return NULL;
    }
    SharedMap *data=PyMem_Calloc(1,sizeof(SharedMap));
    if (!data) return PyErr_NoMemory();
    data->mass=*mass; data->spin=*spin; data->dt=dt; data->capacity=capacity;
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
    if (!PyTuple_Check(branches) || PyTuple_GET_SIZE(branches)<1 || PyTuple_GET_SIZE(branches)>27) {
        PyErr_SetString(PyExc_ValueError,"三个有限限滑端口的分区数不一致"); goto failed;
    }
    data->branch_count=(int)PyTuple_GET_SIZE(branches);
    for (int i=0; i<data->branch_count; ++i) {
        SharedBranch *branch=&data->branches[i];
        PyObject *input=PyTuple_GET_ITEM(branches,i);
        if (!tuple_fields(input,8)) goto failed;
        PyObject *partition=PyTuple_GET_ITEM(input,0),*local=PyTuple_GET_ITEM(input,5),*shaft=PyTuple_GET_ITEM(input,7);
        if (!tuple_fields(partition,3) || !tuple_fields(local,4) || !tuple_fields(shaft,2)
            || !vector(PyTuple_GET_ITEM(partition,1),branch->offset,9)
            || !vector(PyTuple_GET_ITEM(partition,2),branch->modes,3)
            || !vector(PyTuple_GET_ITEM(input,1),branch->mc,9)
            || !vector(PyTuple_GET_ITEM(input,2),branch->ml,9)
            || !vector(PyTuple_GET_ITEM(shaft,0),branch->mg,9)) goto failed;
        PyObject *projections=PyTuple_GET_ITEM(partition,0);
        if (!PyTuple_Check(projections) || PyTuple_GET_SIZE(projections)>3) {
            PyErr_SetString(PyExc_ValueError,"限滑投影数不一致"); goto failed;
        }
        branch->projection_count=(int)PyTuple_GET_SIZE(projections);
        for (int j=0; j<branch->projection_count; ++j) {
            PyObject *projection=PyTuple_GET_ITEM(projections,j);
            if (!tuple_fields(projection,3) || !vector(PyTuple_GET_ITEM(projection,0),branch->gradients[j],9)
                || !vector(PyTuple_GET_ITEM(projection,1),branch->responses[j],9)) goto failed;
            branch->factors[j]=PyFloat_AsDouble(PyTuple_GET_ITEM(projection,2));
            if (PyErr_Occurred()) goto failed;
        }
        PyObject *response=PyTuple_GET_ITEM(local,0);
        int n=hard ? 4 : 3;
        if (!tuple_fields(response,n)) goto failed;
        for (int j=0; j<n; ++j) if (!vector(PyTuple_GET_ITEM(response,j),branch->port_response[j],n)) goto failed;
        PyObject *plans=PyTuple_GET_ITEM(shaft,1);
        if (!PyTuple_Check(plans) || PyTuple_GET_SIZE(plans)<1 || PyTuple_GET_SIZE(plans)>45) {
            PyErr_SetString(PyExc_ValueError,"实体轴有序分区数不一致"); goto failed;
        }
        branch->plan_count=(int)PyTuple_GET_SIZE(plans);
        for (int j=0; j<branch->plan_count; ++j) {
            SharedPortPlan *plan=&branch->plans[j];
            PyObject *source=PyTuple_GET_ITEM(plans,j);
            if (!tuple_fields(source,hard ? 4 : 2) || !vector(PyTuple_GET_ITEM(source,0),plan->modes,3)) goto failed;
            if (hard) {
                plan->sign=PyFloat_AsDouble(PyTuple_GET_ITEM(source,1));
                plan->slope=PyFloat_AsDouble(PyTuple_GET_ITEM(source,2));
                if (PyErr_Occurred()) goto failed;
            }
            if (!matrix_values(PyTuple_GET_ITEM(source,hard ? 3 : 1),&plan->columns[0][0],3,3)) goto failed;
        }
    }
    PyObject *result=PyCapsule_New(data,shared_map_name,release_shared_map);
    if (!result) goto failed;
    return result;
failed:
    PyMem_Free(data); return NULL;
}
static void shared_projection(const SharedBranch *branch,double values[9]) {
    double terms[9];
    for (int i=0; i<branch->projection_count; ++i) {
        for (int a=0; a<9; ++a) terms[a]=branch->gradients[i][a]*values[a];
        double scale=branch->factors[i]*compensated(terms,9);
        for (int a=0; a<9; ++a) values[a]=values[a]-scale*branch->responses[i][a];
    }
}
static int shared_port_state(const SharedMap *data,const SharedBranch *branch,const double free[4],
                             double values[4],int *index) {
    double speeds[4],reduced[3],gear_free=0.;
    const int ports[3]={0,2,3};
    if (data->hard) {
        gear_free=free[1]/(data->dt*branch->port_response[1][1]);
        for (int i=0; i<3; ++i) reduced[i]=free[ports[i]]-branch->port_response[ports[i]][1]*free[1]
                                                      /branch->port_response[1][1];
    }
    for (int k=0; k<branch->plan_count; ++k) {
        const SharedPortPlan *plan=&branch->plans[k];
        if (data->hard) {
            if (!shaft_trial(free,branch->port_response,data->dt,data->capacity,0.,data->efficiency,
                gear_free,reduced,plan->modes,plan->sign,plan->slope,plan->columns,values,speeds)) continue;
        } else {
            double capacities[3]={data->capacity,data->synchronizer,0.},rhs[3],terms[3],sync_values[3];
            for (int i=0; i<3; ++i) rhs[i]=plan->modes[i]==0. ? free[i]/data->dt : plan->modes[i]*capacities[i];
            for (int i=0; i<3; ++i) {
                for (int j=0; j<3; ++j) terms[j]=plan->columns[j][i]*rhs[j];
                sync_values[i]=compensated(terms,3);
            }
            int feasible=1;
            for (int i=0; i<3; ++i) {
                for (int j=0; j<3; ++j) terms[j]=branch->port_response[i][j]*sync_values[j];
                double speed=free[i]-data->dt*compensated(terms,3);
                if (fabs(sync_values[i])>capacities[i]+PORT_TOLERANCE
                    || (plan->modes[i]==0. ? fabs(speed)>PORT_TOLERANCE : plan->modes[i]*speed < -PORT_TOLERANCE)) feasible=0;
            }
            if (!feasible) continue;
            values[0]=sync_values[0]; values[1]=sync_values[1]; values[2]=0.; values[3]=sync_values[2];
        }
        *index=k; return 1;
    }
    PyErr_SetString(PyExc_ArithmeticError,data->hard ? "实体输入轴/离合/齿轮/制动共同末状态无可行解"
                                                  : "实体输入轴/离合/同步器/制动共同末状态无可行解");
    return 0;
}
static PyObject *shared_map_state(PyObject *self,PyObject *args,PyObject *kwargs) {
    PyObject *coefficients,*input,*loads,*wheel_loads,*supported;
    int warm;
    static char *names[]={"coefficients","state","loads","wheel_loads","supported","warm_branch",NULL};
    if (!PyArg_ParseTupleAndKeywords(args,kwargs,"OOOOOi",names,&coefficients,&input,&loads,&wheel_loads,&supported,&warm)) return NULL;
    SharedMap *data=PyCapsule_GetPointer(coefficients,shared_map_name);
    if (!data) return NULL;
    if (warm<0 || warm>=data->branch_count) { PyErr_SetString(PyExc_IndexError,"共同分区索引越界"); return NULL; }
    double state[11],angular[9],normal[9],load[4],support[4],momentum[3],gyro[3],free[9],terms[9];
    double active[3],road[4]={0.},end[9],port_values[4]={0.};
    if (!vector(input,state,data->bias ? 11 : 9) || !tuple_fields(loads,3)
        || !vector(PyTuple_GET_ITEM(loads,0),angular,9)
        || !vector(wheel_loads,load,4) || !vector(supported,support,4)) return NULL;
    PyObject *normal_object=PyTuple_GET_ITEM(loads,1);
    if (!PyTuple_Check(normal_object)) { PyErr_SetString(PyExc_ValueError,"法向载荷须为元组"); return NULL; }
    int suspension=PyTuple_GET_SIZE(normal_object)!=0;
    if (suspension && !vector(normal_object,normal,9)) return NULL;
    for (int i=0; i<3; ++i) active[i]=data->limits[i];
    if (data->bias) {
        double axial[3]={0.};
        if (data->downstream) for (int i=0; i<3; ++i) {
            for (int a=0; a<9; ++a) terms[a]=data->down_gradients[i][a]*state[a];
            axial[i]=data->inertias[i]*(compensated(terms,9)-data->old_omega[i])/data->dt;
        }
        double output=data->ratio*(state[9]-state[10]);
        double torques[2]={data->share*output-data->final_drive*(data->share*axial[0]+axial[1]),
            (1-data->share)*output-data->final_drive*((1-data->share)*axial[0]+axial[2])};
        for (int i=0; i<2; ++i) if (data->biases[i]>1.) {
            double capacity=fabs(torques[i])*(data->biases[i]-1.)/(2*(data->biases[i]+1.));
            active[i]=capacity<data->limits[i] ? capacity : data->limits[i];
        }
    }
    if (data->rolling) for (int i=0; i<4; ++i) if (support[i]!=0.) {
        double speed=fabs(data->radii[i]*state[i+5]);
        double denominator=speed>data->transition ? speed : data->transition;
        road[i]=data->rolling_coefficients[i]*load[i]*pow(data->radii[i],2.)*state[i+5]/denominator;
    }
    rotor_spin_values(&data->spin,state,momentum);
    gyro[0]=momentum[1]*state[2]-momentum[2]*state[1];
    gyro[1]=momentum[2]*state[0]-momentum[0]*state[2];
    gyro[2]=momentum[0]*state[1]-momentum[1]*state[0];
    known_values(&data->mass,data->base,gyro,angular,suspension ? normal : NULL,data->dt,
                 data->rolling ? road : NULL,free);
    int branch_index=-1,port_index=-1;
    for (int visit=-1; visit<data->branch_count; ++visit) {
        int index=visit<0 ? warm : visit;
        if (visit>=0 && index==warm) continue;
        const SharedBranch *branch=&data->branches[index];
        double projected[9];
        for (int a=0; a<9; ++a) projected[a]=free[a];
        if (data->limited) {
            shared_projection(branch,projected);
            double offset[9];
            for (int a=0; a<9; ++a) offset[a]=data->bias ? 0. : branch->offset[a];
            if (data->bias) {
                for (int i=0; i<3; ++i) if (branch->modes[i]!=0.)
                    for (int a=0; a<9; ++a) offset[a]=offset[a]-data->dt*branch->modes[i]*active[i]*data->differential_responses[i][a];
                shared_projection(branch,offset);
            }
            for (int a=0; a<9; ++a) projected[a]=projected[a]+offset[a];
        }
        double port_free[4]={0.};
        for (int i=0; i<(data->hard ? 4 : 3); ++i) {
            for (int a=0; a<9; ++a) terms[a]=data->ports[i][a]*projected[a];
            port_free[i]=compensated(terms,9);
        }
        if (!shared_port_state(data,branch,port_free,port_values,&port_index)) return NULL;
        for (int a=0; a<9; ++a) end[a]=projected[a]-data->dt*(port_values[0]*branch->mc[a]
                                                +port_values[2]*branch->ml[a]+port_values[1]*branch->mg[a]);
        int feasible=1;
        for (int i=0; i<3; ++i) {
            if (data->damping[i]==0. || active[i]==0.) continue;
            for (int a=0; a<9; ++a) terms[a]=data->differential[i][a]*end[a];
            double viscous=data->damping[i]*compensated(terms,9);
            double torque=branch->modes[i]!=0. ? branch->modes[i]*active[i] : viscous;
            double bounded=viscous<active[i] ? viscous : active[i];
            double expected=bounded > -active[i] ? bounded : -active[i];
            if (fabs(torque-expected)>PORT_TOLERANCE) { feasible=0; break; }
        }
        if (feasible) { branch_index=index; break; }
    }
    if (branch_index<0) { PyErr_SetString(PyExc_ArithmeticError,"限滑/离合共同末状态无可行分区"); return NULL; }
    PyObject *result=PyTuple_New(data->bias ? 11 : 9);
    if (!result) return NULL;
    for (int a=0; a<(data->bias ? 11 : 9); ++a) {
        double value=a<9 ? end[a] : port_values[a==9 ? 1 : 2];
        PyObject *number=PyFloat_FromDouble(value);
        if (!number) { Py_DECREF(result); return NULL; }
        PyTuple_SET_ITEM(result,a,number);
    }
    return Py_BuildValue("(NOdd dii(dddd)(ddd))",result,PyTuple_GET_ITEM(loads,2),
        port_values[0],port_values[2],port_values[1],branch_index,port_index,
        road[0],road[1],road[2],road[3],active[0],active[1],active[2]);
}
'''
Path('logs/physics/PHYS-PERF-01/shared-map-body.c').write_text(block,encoding='utf-8')
