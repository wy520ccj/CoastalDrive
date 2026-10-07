from pathlib import Path
root=Path.cwd();p=root/'src/mechanical_kernels.c';s=p.read_text(encoding='utf-8')
s=s.replace('double base[9],dt,capacity,efficiency,synchronizer;','double base[9],spin_columns[9][3],dt,capacity,efficiency,synchronizer;',1)
s=s.replace('data->mass=*mass; data->spin=*spin; data->dt=dt; data->capacity=capacity;','''data->mass=*mass; data->spin=*spin; data->dt=dt; data->capacity=capacity;
    for (int j=0; j<9; ++j) {
        double unit[9]={0.}; unit[j]=1.;
        rotor_spin_values(spin,unit,data->spin_columns[j]);
    }''',1)
# 映射与其导数共用轴端实体惯性矩计算。
start=s.index('        double axial[3]={0.};',s.index('static PyObject *shared_map_state('));end=s.index('        for (int i=0; i<2; ++i) if (data->biases[i]>1.)',start)
body=s[start:end].replace('double torques[2]={data->share*output-data->final_drive*(data->share*axial[0]+axial[1]),\n            (1-data->share)*output-data->final_drive*((1-data->share)*axial[0]+axial[2])};','torques[0]=data->share*output-data->final_drive*(data->share*axial[0]+axial[1]);\n        torques[1]=(1-data->share)*output-data->final_drive*((1-data->share)*axial[0]+axial[2]);')
helper='static void shared_axle_torques(const SharedMap *data,const double state[11],double torques[2]) {\n    double terms[9];\n'+body+'}\n\n'
s=s[:start]+'        double torques[2];\n        shared_axle_torques(data,state,torques);\n'+s[end:];pos=s.index('static PyObject *shared_map_state(');s=s[:pos]+helper+s[pos:]
block=r'''
/* 同一活动分区的本构解析导数，不改变Newton或线搜索判据。 */
static PyObject *shared_map_jacobian(PyObject *self,PyObject *args,PyObject *kwargs) {
    PyObject *coefficients,*input,*wheel_loads,*supported;
    int branch_index,port_index;
    static char *names[]={"coefficients","state","wheel_loads","supported","branch_index","port_index",NULL};
    if (!PyArg_ParseTupleAndKeywords(args,kwargs,"OOOOii",names,&coefficients,&input,&wheel_loads,&supported,
                                    &branch_index,&port_index)) return NULL;
    SharedMap *data=PyCapsule_GetPointer(coefficients,shared_map_name);
    if (!data) return NULL;
    if (branch_index<0 || branch_index>=data->branch_count) {
        PyErr_SetString(PyExc_IndexError,"共同分区索引越界"); return NULL;
    }
    SharedBranch *branch=&data->branches[branch_index];
    if (port_index<0 || port_index>=branch->plan_count) {
        PyErr_SetString(PyExc_IndexError,"共同端口索引越界"); return NULL;
    }
    const SharedPortPlan *plan=&branch->plans[port_index];
    int variables=data->bias ? 11 : 9;
    double state[11],load[4],support[4],current_spin[3],derivatives[3][11]={{0.}},terms[9];
    if (!vector(input,state,variables) || !vector(wheel_loads,load,4) || !vector(supported,support,4)) return NULL;
    rotor_spin_values(&data->spin,state,current_spin);
    if (data->bias) {
        double torques[2]; shared_axle_torques(data,state,torques);
        for (int axle=0; axle<2; ++axle) {
            double bias=data->biases[axle],weight=axle==0 ? data->share : 1-data->share;
            double coefficient=(bias-1.)/(2*(bias+1.));
            double slope=bias>1. && fabs(torques[axle])*coefficient<data->limits[axle]
                         ? copysign(coefficient,torques[axle]) : 0.;
            for (int j=0; j<variables; ++j)
                derivatives[axle][j]=slope*(weight*data->ratio*((double)(j==9)-(double)(j==10))
                    -(data->downstream && j<9 ? data->final_drive/data->dt
                      *(weight*data->inertias[0]*data->down_gradients[0][j]
                        +data->inertias[axle+1]*data->down_gradients[axle+1][j]) : 0.));
        }
    }
    PyObject *columns=PyList_New(variables);
    if (!columns) return NULL;
    for (int j=0; j<variables; ++j) {
        double gyro[3]={0.},input_response[9]={0.},direction[9];
        if (j<9) {
            const double *spin=data->spin_columns[j];
            gyro[0]=spin[1]*state[2]-spin[2]*state[1];
            gyro[1]=spin[2]*state[0]-spin[0]*state[2];
            gyro[2]=spin[0]*state[1]-spin[1]*state[0];
        }
        if (j<3) {
            double unit[3]={0.},second[3]; unit[j]=1.;
            second[0]=current_spin[1]*unit[2]-current_spin[2]*unit[1];
            second[1]=current_spin[2]*unit[0]-current_spin[0]*unit[2];
            second[2]=current_spin[0]*unit[1]-current_spin[1]*unit[0];
            for (int a=0; a<3; ++a) gyro[a]=gyro[a]+second[a];
        }
        for (int a=0; a<3; ++a) input_response[a]=gyro[a];
        mass_response_values(&data->mass,input_response,direction);
        if (data->rolling && j>=5 && j<9) {
            int i=j-5;
            double slope=support[i]!=0. && fabs(data->radii[i]*state[j])<data->transition
                ? data->rolling_coefficients[i]*load[i]*pow(data->radii[i],2.)/data->transition : 0.;
            double rolling_input[9]={0.},rolling_direction[9]; rolling_input[j]=-slope;
            mass_response_values(&data->mass,rolling_input,rolling_direction);
            for (int a=0; a<9; ++a) direction[a]=direction[a]+rolling_direction[a];
        }
        if (data->bias) for (int i=0; i<3; ++i) if (branch->modes[i]!=0.)
            for (int a=0; a<9; ++a) direction[a]=direction[a]-branch->modes[i]*derivatives[i][j]*data->differential_responses[i][a];
        shared_projection(branch,direction);
        double port_direction[4]={0.},dc,dg,dl;
        for (int i=0; i<(data->hard ? 4 : 3); ++i) {
            for (int a=0; a<9; ++a) terms[a]=data->ports[i][a]*direction[a];
            port_direction[i]=compensated(terms,9);
        }
        double rhs[3],values[3];
        if (data->hard) {
            const int ports[3]={0,2,3};
            double gear_free=port_direction[1]/branch->port_response[1][1],reduced[3];
            for (int i=0; i<3; ++i) reduced[i]=port_direction[ports[i]]-branch->port_response[ports[i]][1]*gear_free;
            rhs[0]=plan->modes[0]==0. ? reduced[0] : 0.;
            rhs[1]=plan->modes[1]==0. ? reduced[1] : plan->slope*gear_free;
            rhs[2]=plan->modes[2]==0. ? reduced[2] : 0.;
            for (int i=0; i<3; ++i) {
                for (int k=0; k<3; ++k) terms[k]=plan->columns[k][i]*rhs[k];
                values[i]=compensated(terms,3);
            }
            dc=values[0]; dl=values[1];
            for (int k=0; k<3; ++k) terms[k]=branch->port_response[1][ports[k]]*values[k]/branch->port_response[1][1];
            dg=gear_free-compensated(terms,3);
        } else {
            for (int i=0; i<3; ++i) rhs[i]=plan->modes[i]==0. ? port_direction[i] : 0.;
            for (int i=0; i<3; ++i) {
                for (int k=0; k<3; ++k) terms[k]=plan->columns[k][i]*rhs[k];
                values[i]=compensated(terms,3);
            }
            dc=values[0]; dg=values[1]; dl=0.;
        }
        PyObject *column=PyTuple_New(variables);
        if (!column) { Py_DECREF(columns); return NULL; }
        for (int a=0; a<variables; ++a) {
            double end_column=a<9 ? data->dt*(direction[a]-dc*branch->mc[a]-dg*branch->mg[a]-dl*branch->ml[a])
                                 : (a==9 ? dg : dl);
            PyObject *number=PyFloat_FromDouble((double)(a==j)-end_column);
            if (!number) { Py_DECREF(column); Py_DECREF(columns); return NULL; }
            PyTuple_SET_ITEM(column,a,number);
        }
        PyList_SET_ITEM(columns,j,column);
    }
    return columns;
}
'''
s=s.replace('static PyMethodDef methods[]',block+'\nstatic PyMethodDef methods[]',1);s=s.replace('static PyMethodDef methods[] = {','static PyMethodDef methods[] = {\n    {"shared_map_jacobian", (PyCFunction)shared_map_jacobian, METH_VARARGS | METH_KEYWORDS, "原九/十一维共同状态活动分区解析导数"},',1);p.write_text(s,encoding='utf-8')
p=root/'src/tire_drivetrain.py';s=p.read_text(encoding='utf-8');s=s.replace('    shared_map_coefficients,','    shared_map_coefficients,\n    shared_map_jacobian,',1);start=s.index('    spin_columns = None');end=s.index('    def shared(guess):',start);s=s[:start]+'''    def shared_jacobian_columns(state):
        return shared_map_jacobian(shared_map, state, tuple(frame.load for frame in frames),
                                   tuple(frame.supported for frame in frames), shared_branch, shared_port_index)

'''+s[end:];p.write_text(s,encoding='utf-8')
