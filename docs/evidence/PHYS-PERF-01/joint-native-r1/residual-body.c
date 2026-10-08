/* 同一末状态下四轮接触与制动残差；原点积/本构/误差尺度保持。 */
static PyObject *wheel_residuals(PyObject *self,PyObject *args) {
    PyObject *coefficients,*state_object,*velocity_object,*forces_object,*modes_object,*previous_object;
    PyObject *parameters_object,*hardware_object,*rolling_object,*moment_x_object,*moment_y_object,*compliance_object,*hypot;
    if (!PyArg_ParseTuple(args,"OOOOOOOOOOOOO",&coefficients,&state_object,&velocity_object,&forces_object,
        &modes_object,&previous_object,&parameters_object,&hardware_object,&rolling_object,&moment_x_object,
        &moment_y_object,&compliance_object,&hypot)) return NULL;
    WheelMap *packet=PyCapsule_GetPointer(coefficients,wheel_map_name);
    if (!packet) return NULL;
    double state[9],velocity[3],forces[12],previous[8],parameters[12],hardware[20],rolling[4];
    double moment_x[12],moment_y[12],compliance[4];
    if (!vector(state_object,state,9) || !vector(velocity_object,velocity,3)
        || !matrix_values(forces_object,forces,4,3) || !matrix_values(previous_object,previous,4,2)
        || !matrix_values(parameters_object,parameters,4,3) || !matrix_values(hardware_object,hardware,4,5)
        || !vector(rolling_object,rolling,4) || !matrix_values(moment_x_object,moment_x,4,3)
        || !matrix_values(moment_y_object,moment_y,4,3) || !vector(compliance_object,compliance,4)) return NULL;
    PyObject *modes=PySequence_Fast(modes_object,"轮端模式须为四轮序列");
    if (!modes) return NULL;
    if (PySequence_Fast_GET_SIZE(modes)!=4) { Py_DECREF(modes); PyErr_SetString(PyExc_ValueError,"轮端模式须为四轮序列"); return NULL; }
    double maximum=0.,brake_error=0.,dt=packet->shared->dt;
    for (int i=0;i<4;++i) {
        const char *mode=PyUnicode_AsUTF8(PySequence_Fast_GET_ITEM(modes,i));
        if (!mode) { Py_DECREF(modes); return NULL; }
        const double *tangent=packet->load.tangents+3*i,*axle=packet->load.axles+3*i;
        double radius=packet->shared->radii[i],speed[2],slip[2],error,terms[9];
        wheel_velocity_values(state,velocity,i+5,tangent,axle,moment_x+3*i,moment_y+3*i,radius,speed,slip);
        if (strcmp(mode,"sticking")==0) {
            const double *rx=packet->load.responses+27*i,*ry=rx+9;
            for (int a=0;a<9;++a) terms[a]=(a<3 ? moment_x[3*i+a] : a==i+5 ? -radius : 0.)*rx[a];
            double scale_x=dt*(1/packet->load.mass+compensated(terms,9));
            for (int a=0;a<9;++a) terms[a]=(a<3 ? moment_y[3*i+a] : 0.)*ry[a];
            double scale_y=dt*(1/packet->load.mass+compensated(terms,9));
            if (!tire_norm(hypot,slip[0]/scale_x,slip[1]/scale_y,&error)) { Py_DECREF(modes); return NULL; }
        } else {
            const double *p=parameters+3*i,*h=hardware+5*i;
            double denominator=fabs(speed[0])>h[0] ? fabs(speed[0]) : h[0],target[2];
            if (compliance[i]!=0.) {
                double deformation[2],rate[2],patch[2],kappa,alpha;
                const char *contact_mode;
                if (!tire_contact_values(forces+3*i,previous+2*i,slip,denominator,rolling[i]!=0.,p[0],p[1],p[2],
                    dt,h[1],h[2],h[3],h[4],hypot,target,deformation,rate,patch,&kappa,&alpha,&contact_mode)) {
                    Py_DECREF(modes); return NULL;
                }
            } else if (!tire_curve_values(slip[0]/denominator,atan2(speed[1],denominator),p[0],p[1],p[2],h[3],h[4],hypot,target)) {
                Py_DECREF(modes); return NULL;
            }
            if (!tire_norm(hypot,forces[3*i]-target[0],forces[3*i+1]-target[1],&error)) { Py_DECREF(modes); return NULL; }
        }
        if (error>maximum) maximum=error;
        for (int a=0;a<9;++a) terms[a]=packet->brake_gradients[i][a]*state[a];
        double speed_brake=compensated(terms,9);
        const double *rb=packet->load.responses+27*i+18;
        for (int a=0;a<9;++a) terms[a]=packet->brake_gradients[i][a]*rb[a];
        double response=compensated(terms,9),brake=forces[3*i+2],target=brake+speed_brake/(dt*response);
        target=target<packet->brakes[i] ? target : packet->brakes[i];
        target=target>-packet->brakes[i] ? target : -packet->brakes[i];
        double brake_residual=fabs(brake-target);
        if (brake_residual>brake_error) brake_error=brake_residual;
    }
    Py_DECREF(modes);
    return Py_BuildValue("(dd)",maximum,brake_error);
}

/* 原法向力差与六分量几何共轭冲量，仍使用逐分量四项补偿和。 */
static PyObject *suspension_residuals(PyObject *self,PyObject *args) {
    PyObject *force_object,*target_force_object,*gradients_object,*target_gradients_object;
    double dt,forces[4],target_forces[4],gradients[24],target_gradients[24],normal_error=0.,geometry_error=0.,terms[4];
    if (!PyArg_ParseTuple(args,"OOOOd",&force_object,&target_force_object,&gradients_object,&target_gradients_object,&dt)) return NULL;
    if (!vector(force_object,forces,4) || !vector(target_force_object,target_forces,4)
        || !matrix_values(gradients_object,gradients,4,6) || !matrix_values(target_gradients_object,target_gradients,4,6)) return NULL;
    for (int i=0;i<4;++i) {
        double error=fabs(forces[i]-target_forces[i]);
        if (error>normal_error) normal_error=error;
    }
    for (int a=0;a<6;++a) {
        for (int i=0;i<4;++i) terms[i]=forces[i]*(target_gradients[6*i+a]-gradients[6*i+a]);
        double error=fabs(compensated(terms,4));
        if (error>geometry_error) geometry_error=error;
    }
    return Py_BuildValue("(dd)",normal_error,dt*geometry_error);
}
