/* 本次轮端方程的固定输入；暖分区仍逐次写回原list。 */
typedef struct {
    WheelMap *map;
    int wheel,rolling;
    double base[9],velocity[3],active[3],tangent[3],axle[3],moment_x[3],moment_y[3];
    double radius,previous[2],parameters[3],hardware[5];
    PyObject *warm_branches,*warm_modes,*hypot;
} WheelForce;

static int wheel_force_values(void *context,double fx,double fy,int jacobian,double *result) {
    WheelForce *data=context;
    double state[9],velocity[3],brake;
    int selected,mode;
    int warm=(int)PyLong_AsLong(PyList_GET_ITEM(data->warm_branches,data->wheel));
    if (PyErr_Occurred() || !wheel_map_values(data->map,data->wheel,data->base,data->velocity,fx,fy,data->active,
        warm,data->warm_modes,data->tangent,data->axle,state,velocity,&brake,&selected,&mode)) return 0;
    PyObject *updated=PyLong_FromLong(selected);
    if (!updated || PyList_SetItem(data->warm_branches,data->wheel,updated)<0) return 0;
    double force[2]={fx,fy},speed[2],slip[2],gradients[2][3],terms[3];
    if (jacobian) {
        if (!wheel_derivative_values(data->map,data->wheel,selected,mode,state,velocity,data->moment_x,data->moment_y,
            data->radius,data->tangent,data->axle,speed,slip,gradients)) return 0;
    } else {
        for (int a=0;a<3;++a) terms[a]=velocity[a]*data->tangent[a];
        speed[0]=compensated(terms,3);
        for (int a=0;a<3;++a) terms[a]=state[a]*data->moment_x[a];
        speed[0]=speed[0]+compensated(terms,3);
        for (int a=0;a<3;++a) terms[a]=velocity[a]*data->axle[a];
        speed[1]=compensated(terms,3);
        for (int a=0;a<3;++a) terms[a]=state[a]*data->moment_y[a];
        speed[1]=speed[1]+compensated(terms,3);
        slip[0]=data->radius*state[data->wheel+5]-speed[0]; slip[1]=-speed[1];
    }
    double denominator=fabs(speed[0]);
    if (data->hardware[0]>denominator) denominator=data->hardware[0];
    double dt=data->map->shared->dt;
    if (jacobian) {
        double slip_jacobian[4]={gradients[0][0],gradients[1][0],gradients[0][1],gradients[1][1]};
        double denominator_gradient[2]={0.},target[4];
        if (fabs(speed[0])>data->hardware[0])
            for (int a=0;a<2;++a) denominator_gradient[a]=copysign(1.,speed[0])*gradients[a][2];
        if (!tire_jacobian_values(force,data->previous,slip,slip_jacobian,denominator,denominator_gradient,data->rolling,
            data->parameters[0],data->parameters[1],data->parameters[2],dt,data->hardware[1],data->hardware[2],
            data->hardware[3],data->hardware[4],data->hypot,target)) return 0;
        result[0]=1-target[0]; result[1]=-target[1]; result[2]=-target[2]; result[3]=1-target[3];
    } else {
        double target[2],deformation[2],rate[2],patch[2],kappa,alpha;
        const char *contact_mode;
        if (!tire_contact_values(force,data->previous,slip,denominator,data->rolling,
            data->parameters[0],data->parameters[1],data->parameters[2],dt,data->hardware[1],data->hardware[2],
            data->hardware[3],data->hardware[4],data->hypot,target,deformation,rate,patch,&kappa,&alpha,&contact_mode)) return 0;
        result[0]=fx-target[0]; result[1]=fy-target[1];
    }
    return 1;
}
static int wheel_newton_values(WheelForce *data,double tolerance,double force[2],double *final_error) {
    double error=0.;
    for (int iteration=0;iteration<20;++iteration) {
        double residual[2],matrix[4];
        if (!wheel_force_values(data,force[0],force[1],0,residual)
            || !tire_norm(data->hypot,residual[0],residual[1],&error)) return 0;
        if (error<tolerance) { *final_error=error; return 1; }
        if (!wheel_force_values(data,force[0],force[1],1,matrix)) return 0;
        double determinant=matrix[0]*matrix[3]-matrix[1]*matrix[2];
        if (determinant==0.) { PyErr_SetString(PyExc_ZeroDivisionError,"轮胎Jacobian行列式为零"); return 0; }
        double dx=(matrix[3]*residual[0]-matrix[1]*residual[1])/determinant;
        double dy=(matrix[0]*residual[1]-matrix[2]*residual[0])/determinant;
        int exponent;
        for (exponent=0;exponent<12;++exponent) {
            double scale=ldexp(1.,-exponent),candidate_x=force[0]-scale*dx,candidate_y=force[1]-scale*dy;
            double next[2],next_error;
            if (!wheel_force_values(data,candidate_x,candidate_y,0,next) || !tire_norm(data->hypot,next[0],next[1],&next_error)) return 0;
            if (next_error<error) { force[0]=candidate_x; force[1]=candidate_y; break; }
        }
        if (exponent==12) { rolling_root_failure("轮胎隐式积分不收敛：残差 ",error); return 0; }
    }
    rolling_root_failure("轮胎隐式积分超过20次迭代：残差 ",error); return 0;
}
static PyObject *wheel_force_solution(PyObject *self,PyObject *args) {
    WheelForce context;
    PyObject *coefficients,*base,*velocity,*active,*tangent,*axle,*moment_x,*moment_y,*previous,*parameters,*hardware,*initial;
    double tolerance,force[2],error;
    if (!PyArg_ParseTuple(args,"Oi" "OOOOOOOOO" "dOOOpdOO",&coefficients,&context.wheel,&base,&velocity,&active,
        &context.warm_branches,&context.warm_modes,&tangent,&axle,&moment_x,&moment_y,&context.radius,&previous,
        &parameters,&hardware,&context.rolling,&tolerance,&initial,&context.hypot)) return NULL;
    context.map=PyCapsule_GetPointer(coefficients,wheel_map_name);
    if (!context.map) return NULL;
    if (context.wheel<0 || context.wheel>=4) { PyErr_SetString(PyExc_IndexError,"轮端索引越界"); return NULL; }
    if (!vector(base,context.base,9) || !vector(velocity,context.velocity,3) || !vector(active,context.active,3)
        || !vector(tangent,context.tangent,3) || !vector(axle,context.axle,3) || !vector(moment_x,context.moment_x,3)
        || !vector(moment_y,context.moment_y,3) || !vector(previous,context.previous,2)
        || !vector(parameters,context.parameters,3) || !vector(hardware,context.hardware,5) || !vector(initial,force,2)) return NULL;
    int solved=context.rolling ? rolling_root_values(wheel_force_values,&context,context.parameters[0],tolerance,force,context.hypot,&error)
                               : wheel_newton_values(&context,tolerance,force,&error);
    if (!solved) return NULL;
    return Py_BuildValue("(ddd)",force[0],force[1],error);
}
