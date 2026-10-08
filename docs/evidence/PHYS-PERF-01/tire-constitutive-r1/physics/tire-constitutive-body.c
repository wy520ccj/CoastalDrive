/* 保留CPython hypot的原舍入；其余本构算式沿原次序直接计算。 */
static int tire_norm(PyObject *hypot_function,double x,double y,double *value) {
    PyObject *result=PyObject_CallFunction(hypot_function,"dd",x,y);
    if (!result) return 0;
    *value=PyFloat_AsDouble(result); Py_DECREF(result); return !PyErr_Occurred();
}
static int tire_curve_values(double kappa,double alpha,double grip,double cx,double cy,
    double shape,double curvature,PyObject *hypot_function,double target[2]) {
    target[0]=target[1]=0.;
    if (grip==0.) return 1;
    double qx=cx*kappa,qy=-cy*tan(alpha),magnitude;
    if (!tire_norm(hypot_function,qx,qy,&magnitude)) return 0;
    if (magnitude==0.) return 1;
    double n=magnitude/(shape*grip);
    double force=grip*sin(shape*atan(n-curvature*(n-atan(n))));
    target[0]=force*qx/magnitude; target[1]=force*qy/magnitude;
    return 1;
}
static PyObject *tire_combined_force(PyObject *self,PyObject *args) {
    double kappa,alpha,grip,cx,cy,shape,curvature,target[2];
    PyObject *hypot_function;
    if (!PyArg_ParseTuple(args,"dddddddO",&kappa,&alpha,&grip,&cx,&cy,&shape,&curvature,&hypot_function)) return NULL;
    if (!tire_curve_values(kappa,alpha,grip,cx,cy,shape,curvature,hypot_function,target)) return NULL;
    return Py_BuildValue("(dd)",target[0],target[1]);
}
static PyObject *tire_contact_force(PyObject *self,PyObject *args) {
    PyObject *force_object,*previous_object,*slip_object,*hypot_function;
    double denominator,grip,cx,cy,dt,stiffness,damping,shape,curvature;
    int rolling;
    if (!PyArg_ParseTuple(args,"OOOdpddddddddO",&force_object,&previous_object,&slip_object,&denominator,&rolling,
        &grip,&cx,&cy,&dt,&stiffness,&damping,&shape,&curvature,&hypot_function)) return NULL;
    double force[2],previous[2],slip[2],rate[2],deformation[2],patch[2],target[2];
    if (!vector(force_object,force,2) || !vector(previous_object,previous,2) || !vector(slip_object,slip,2)) return NULL;
    double impedance=stiffness*dt+damping;
    for (int i=0; i<2; ++i) {
        rate[i]=(force[i]-stiffness*previous[i])/impedance;
        deformation[i]=previous[i]+dt*rate[i]; patch[i]=slip[i]-rate[i];
    }
    double kappa=patch[0]/denominator,alpha=atan2(-patch[1],denominator);
    const char *mode;
    if (rolling) {
        if (!tire_curve_values(kappa,alpha,grip,cx,cy,shape,curvature,hypot_function,target)) return NULL;
        mode="compliant-rolling";
    } else {
        double trial[2],magnitude;
        for (int i=0; i<2; ++i) trial[i]=stiffness*previous[i]+impedance*slip[i];
        if (!tire_norm(hypot_function,trial[0],trial[1],&magnitude)) return NULL;
        if (magnitude<=grip) {
            target[0]=trial[0]; target[1]=trial[1]; mode="compliant-sticking";
        } else {
            for (int i=0; i<2; ++i) target[i]=grip*trial[i]/magnitude;
            mode="compliant-sliding";
        }
    }
    return Py_BuildValue("((dd)(dd)(dd)(dd)dds)",target[0],target[1],deformation[0],deformation[1],
        rate[0],rate[1],patch[0],patch[1],kappa,alpha,mode);
}
static PyObject *tire_contact_jacobian(PyObject *self,PyObject *args) {
    PyObject *force_object,*previous_object,*slip_object,*slip_jacobian_object,*denominator_gradient_object,*hypot_function;
    double denominator,grip,cx,cy,dt,stiffness,damping,shape,curvature;
    int rolling;
    if (!PyArg_ParseTuple(args,"OOOOdOpddddddddO",&force_object,&previous_object,&slip_object,&slip_jacobian_object,
        &denominator,&denominator_gradient_object,&rolling,&grip,&cx,&cy,&dt,&stiffness,&damping,&shape,&curvature,&hypot_function)) return NULL;
    if (grip==0.) return Py_BuildValue("((dd)(dd))",0.,0.,0.,0.);
    double force[2],previous[2],slip[2],slip_jacobian[4],denominator_gradient[2],result[4];
    if (!vector(force_object,force,2) || !vector(previous_object,previous,2) || !vector(slip_object,slip,2)
        || !matrix_values(slip_jacobian_object,slip_jacobian,2,2)
        || !vector(denominator_gradient_object,denominator_gradient,2)) return NULL;
    double impedance=stiffness*dt+damping;
    if (!rolling) {
        double trial[2],magnitude,trial_jacobian[4],projection[4],terms[2];
        for (int i=0; i<2; ++i) trial[i]=stiffness*previous[i]+impedance*slip[i];
        if (!tire_norm(hypot_function,trial[0],trial[1],&magnitude)) return NULL;
        for (int i=0; i<4; ++i) trial_jacobian[i]=impedance*slip_jacobian[i];
        if (magnitude<=grip) {
            for (int i=0; i<4; ++i) result[i]=trial_jacobian[i];
        } else {
            for (int i=0; i<2; ++i) for (int j=0; j<2; ++j)
                projection[2*i+j]=grip/magnitude*((double)(i==j)-trial[i]*trial[j]/pow(magnitude,2.));
            for (int i=0; i<2; ++i) for (int j=0; j<2; ++j) {
                for (int a=0; a<2; ++a) terms[a]=projection[2*i+a]*trial_jacobian[2*a+j];
                result[2*i+j]=compensated(terms,2);
            }
        }
    } else {
        double patch[2],q[2],q_jacobian[4],radial_jacobian[4],magnitude,terms[2];
        const double stiffnesses[2]={cx,cy};
        for (int i=0; i<2; ++i) {
            patch[i]=slip[i]-(force[i]-stiffness*previous[i])/impedance;
            q[i]=stiffnesses[i]*patch[i]/denominator;
            for (int j=0; j<2; ++j) {
                double patch_jacobian=slip_jacobian[2*i+j]-(double)(i==j)/impedance;
                q_jacobian[2*i+j]=(stiffnesses[i]*patch_jacobian-q[i]*denominator_gradient[j])/denominator;
            }
        }
        if (!tire_norm(hypot_function,q[0],q[1],&magnitude)) return NULL;
        if (magnitude==0.) {
            for (int i=0; i<4; ++i) result[i]=q_jacobian[i];
        } else {
            double n=magnitude/(shape*grip),u=n-curvature*(n-atan(n));
            double angle=shape*atan(u),ratio=grip*sin(angle)/magnitude;
            double radial=cos(angle)*(1-curvature+curvature/(1+n*n))/(1+u*u);
            for (int i=0; i<2; ++i) for (int j=0; j<2; ++j)
                radial_jacobian[2*i+j]=ratio*(double)(i==j)+(radial-ratio)*(q[i]/magnitude)*(q[j]/magnitude);
            for (int i=0; i<2; ++i) for (int j=0; j<2; ++j) {
                for (int a=0; a<2; ++a) terms[a]=radial_jacobian[2*i+a]*q_jacobian[2*a+j];
                result[2*i+j]=compensated(terms,2);
            }
        }
    }
    return Py_BuildValue("((dd)(dd))",result[0],result[1],result[2],result[3]);
}
