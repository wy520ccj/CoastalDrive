/* 同一轮端活动分区的完整解析导数；输入末状态来自原轮力映射。 */
static PyObject *wheel_map_derivatives(PyObject *self,PyObject *args) {
    PyObject *coefficients,*state_object,*velocity_object,*moment_x_object,*moment_y_object,*tangent_object,*axle_object;
    int wheel,branch_index,port_index;
    double radius;
    if (!PyArg_ParseTuple(args,"OiiiOOOOdOO",&coefficients,&wheel,&branch_index,&port_index,
        &state_object,&velocity_object,&moment_x_object,&moment_y_object,&radius,&tangent_object,&axle_object)) return NULL;
    WheelMap *packet=PyCapsule_GetPointer(coefficients,wheel_map_name);
    if (!packet) return NULL;
    SharedMap *data=packet->shared;
    if (wheel<0 || wheel>=4 || branch_index<0 || branch_index>=data->branch_count) {
        PyErr_SetString(PyExc_IndexError,"轮端导数分区索引越界"); return NULL;
    }
    WheelBranch *wheel_branch=&packet->local[4*branch_index+wheel];
    SharedBranch *branch=&data->branches[branch_index],*local=&wheel_branch->ports;
    if (port_index<0 || port_index>=local->plan_count) {
        PyErr_SetString(PyExc_IndexError,"轮端导数端口索引越界"); return NULL;
    }
    SharedPortPlan *plan=&local->plans[port_index];
    double state[9],velocity[3],moment_x[3],moment_y[3],tangent[3],axle[3],terms[9];
    if (!vector(state_object,state,9) || !vector(velocity_object,velocity,3)
        || !vector(moment_x_object,moment_x,3) || !vector(moment_y_object,moment_y,3)
        || !vector(tangent_object,tangent,3) || !vector(axle_object,axle,3)) return NULL;
    for (int a=0; a<3; ++a) terms[a]=velocity[a]*tangent[a];
    double vx=compensated(terms,3);
    for (int a=0; a<3; ++a) terms[a]=state[a]*moment_x[a];
    vx=vx+compensated(terms,3);
    for (int a=0; a<3; ++a) terms[a]=velocity[a]*axle[a];
    double vy=compensated(terms,3);
    for (int a=0; a<3; ++a) terms[a]=state[a]*moment_y[a];
    vy=vy+compensated(terms,3);
    double gradients[2][3];
    for (int column=0; column<2; ++column) {
        const double *response=wheel_branch->force_responses[column];
        const double *direction=column==0 ? tangent : axle;
        double port_direction[4],rhs[3],dc,dg,dl,db;
        int n=data->hard ? 4 : 3;
        for (int i=0; i<n; ++i) {
            const double *g=i==n-1 ? packet->brake_gradients[wheel] : data->ports[i];
            for (int a=0; a<9; ++a) terms[a]=g[a]*response[a];
            port_direction[i]=compensated(terms,9);
        }
        if (data->hard) {
            int ports[3]={0,2,3};
            double gear_free=port_direction[1]/local->port_response[1][1],reduced[3],output[3];
            for (int j=0; j<3; ++j) reduced[j]=port_direction[ports[j]]-local->port_response[ports[j]][1]*gear_free;
            rhs[0]=plan->modes[0]==0. ? reduced[0] : 0.;
            rhs[1]=plan->modes[1]==0. ? reduced[1] : plan->slope*gear_free;
            rhs[2]=plan->modes[2]==0. ? reduced[2] : 0.;
            for (int a=0; a<3; ++a) {
                for (int j=0; j<3; ++j) terms[j]=plan->columns[j][a]*rhs[j];
                output[a]=compensated(terms,3);
            }
            dc=output[0]; dl=output[1]; db=output[2];
            for (int j=0; j<3; ++j) terms[j]=local->port_response[1][ports[j]]*output[j]/local->port_response[1][1];
            dg=gear_free-compensated(terms,3);
        } else {
            double output[3];
            for (int j=0; j<3; ++j) rhs[j]=plan->modes[j]==0. ? port_direction[j] : 0.;
            for (int a=0; a<3; ++a) {
                for (int j=0; j<3; ++j) terms[j]=plan->columns[j][a]*rhs[j];
                output[a]=compensated(terms,3);
            }
            dc=output[0]; dg=output[1]; db=output[2]; dl=0.;
        }
        double dq[9];
        for (int a=0; a<9; ++a) dq[a]=data->dt*(response[a]-dc*branch->mc[a]-dl*branch->ml[a]-db*local->mc[a]-dg*branch->mg[a]);
        for (int a=0; a<3; ++a) terms[a]=direction[a]*tangent[a];
        double dx=data->dt/packet->load.mass*compensated(terms,3);
        for (int a=0; a<3; ++a) terms[a]=dq[a]*moment_x[a];
        dx=dx+compensated(terms,3);
        for (int a=0; a<3; ++a) terms[a]=direction[a]*axle[a];
        double dy=data->dt/packet->load.mass*compensated(terms,3);
        for (int a=0; a<3; ++a) terms[a]=dq[a]*moment_y[a];
        dy=dy+compensated(terms,3);
        gradients[column][0]=radius*dq[wheel+5]-dx;
        gradients[column][1]=-dy; gradients[column][2]=dx;
    }
    return Py_BuildValue("(dd(dd)[(ddd)(ddd)])",vx,vy,radius*state[wheel+5]-vx,-vy,
        gradients[0][0],gradients[0][1],gradients[0][2],gradients[1][0],gradients[1][1],gradients[1][2]);
}
