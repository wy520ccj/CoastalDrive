/* 局部轮力与端口分区共用原共同映射判据，暖模式按每次尝试直接更新。 */
typedef struct {
    PyObject *shared_owner;
    SharedMap *shared;
    LoadCoefficients load;
    double brake_gradients[4][9],brakes[4];
    SharedBranch local[];
} WheelMap;
static const char *wheel_map_name="CoastalDrive.wheel_map";
static void release_wheel_map(PyObject *object) {
    WheelMap *data=PyCapsule_GetPointer(object,wheel_map_name);
    Py_DECREF(data->shared_owner);
    PyMem_Free(data);
}
static PyObject *wheel_map_coefficients(PyObject *self,PyObject *args) {
    PyObject *shared_object,*load_object,*branches,*gradients,*brakes;
    if (!PyArg_ParseTuple(args,"OOOOO",&shared_object,&load_object,&branches,&gradients,&brakes)) return NULL;
    SharedMap *shared=PyCapsule_GetPointer(shared_object,shared_map_name);
    LoadCoefficients *load=PyCapsule_GetPointer(load_object,load_coefficients_name);
    if (!shared || !load) return NULL;
    WheelMap *data=PyMem_Calloc(1,sizeof(WheelMap)+4*shared->branch_count*sizeof(SharedBranch));
    if (!data) return PyErr_NoMemory();
    data->shared=shared; data->load=*load;
    if (!matrix_values(gradients,&data->brake_gradients[0][0],4,9) || !vector(brakes,data->brakes,4)) goto failed;
    for (int b=0; b<shared->branch_count; ++b) {
        PyObject *input=PyTuple_GET_ITEM(branches,b);
        PyObject *responses=PyTuple_GET_ITEM(input,5),*all_plans=PyTuple_GET_ITEM(input,6);
        for (int w=0; w<4; ++w) {
            SharedBranch *local=&data->local[4*b+w];
            int n=shared->hard ? 4 : 3;
            if (!matrix_values(PyTuple_GET_ITEM(responses,w),&local->port_response[0][0],n, n)) goto failed;
            /* 三端口矩阵的行距仍为四，按原行逐一保存。 */
            if (n==3) for (int j=0; j<3; ++j)
                if (!vector(PyTuple_GET_ITEM(PyTuple_GET_ITEM(responses,w),j),local->port_response[j],3)) goto failed;
            PyObject *plans=PyTuple_GET_ITEM(all_plans,w);
            local->plan_count=(int)PyTuple_GET_SIZE(plans);
            for (int j=0; j<local->plan_count; ++j) {
                PyObject *source=PyTuple_GET_ITEM(plans,j);
                SharedPortPlan *plan=&local->plans[j];
                if (!vector(PyTuple_GET_ITEM(source,0),plan->modes,3)) goto failed;
                if (shared->hard) {
                    plan->sign=PyFloat_AsDouble(PyTuple_GET_ITEM(source,1));
                    plan->slope=PyFloat_AsDouble(PyTuple_GET_ITEM(source,2));
                    if (PyErr_Occurred()) goto failed;
                }
                if (!matrix_values(PyTuple_GET_ITEM(source,shared->hard ? 3 : 1),&plan->columns[0][0],3,3)) goto failed;
            }
            PyObject *wheel=PyTuple_GET_ITEM(PyTuple_GET_ITEM(input,4),w);
            if (!vector(PyTuple_GET_ITEM(wheel,2),local->mc,9)) goto failed;
        }
    }
    Py_INCREF(shared_object); data->shared_owner=shared_object;
    PyObject *result=PyCapsule_New(data,wheel_map_name,release_wheel_map);
    if (!result) { Py_DECREF(shared_object); goto failed; }
    return result;
failed:
    PyMem_Free(data); return NULL;
}
static PyObject *wheel_map_state(PyObject *self,PyObject *args) {
    PyObject *coefficients,*base_object,*velocity_object,*limits_object,*warm_modes,*tangent_object,*axle_object;
    int wheel,warm;
    double fx,fy;
    if (!PyArg_ParseTuple(args,"OiOOddOiOOO",&coefficients,&wheel,&base_object,&velocity_object,&fx,&fy,
                         &limits_object,&warm,&warm_modes,&tangent_object,&axle_object)) return NULL;
    WheelMap *packet=PyCapsule_GetPointer(coefficients,wheel_map_name);
    if (!packet) return NULL;
    SharedMap *data=packet->shared;
    double free[9],velocity[3],active[3],tangent[3],axle[3],terms[9],end[9],values[4];
    if (!vector(base_object,free,9) || !vector(velocity_object,velocity,3) || !vector(limits_object,active,3)
        || !vector(tangent_object,tangent,3) || !vector(axle_object,axle,3)) return NULL;
    const double *rx=packet->load.responses+27*wheel,*ry=rx+9;
    for (int a=0; a<9; ++a) free[a]=free[a]+data->dt*(rx[a]*fx+ry[a]*fy);
    int selected=-1,port_index=-1;
    for (int visit=-1; visit<data->branch_count; ++visit) {
        int index=visit<0 ? warm : visit;
        if (visit>=0 && index==warm) continue;
        SharedBranch *branch=&data->branches[index],*local=&packet->local[4*index+wheel];
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
        int n=data->hard ? 4 : 3;
        for (int i=0; i<n; ++i) {
            const double *gradient=i==n-1 ? packet->brake_gradients[wheel] : data->ports[i];
            for (int a=0; a<9; ++a) terms[a]=gradient[a]*projected[a];
            port_free[i]=compensated(terms,9);
        }
        PyObject *warm_row=PyList_GET_ITEM(warm_modes,index),*old=PyList_GET_ITEM(warm_row,wheel);
        int mode=old==Py_None ? -1 : (int)PyLong_AsLong(old);
        if (PyErr_Occurred() || !shared_port_state(data,local,port_free,packet->brakes[wheel],mode,values,&port_index)) return NULL;
        PyObject *updated=PyLong_FromLong(port_index);
        if (!updated || PyList_SetItem(warm_row,wheel,updated)<0) return NULL;
        for (int a=0; a<9; ++a) end[a]=projected[a]-data->dt*(values[0]*branch->mc[a]+values[2]*branch->ml[a]
                                                       +values[3]*local->mc[a]+values[1]*branch->mg[a]);
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
        if (feasible) { selected=index; break; }
    }
    if (selected<0) { PyErr_SetString(PyExc_ArithmeticError,"限滑/离合/制动共同末状态无可行分区"); return NULL; }
    for (int a=0; a<3; ++a) velocity[a]=velocity[a]+data->dt/packet->load.mass*(fx*tangent[a]+fy*axle[a]);
    PyObject *state=PyTuple_New(9);
    if (!state) return NULL;
    for (int a=0; a<9; ++a) {
        PyObject *number=PyFloat_FromDouble(end[a]);
        if (!number) { Py_DECREF(state); return NULL; }
        PyTuple_SET_ITEM(state,a,number);
    }
    return Py_BuildValue("(N(ddd)d(ii))",state,velocity[0],velocity[1],velocity[2],values[3],selected,port_index);
}
