/* 完整机械输入的连续数值准备；世界读取、末状态求解和冲量提交仍由原入口负责。 */
static double drivetrain_dot(const double *a,const double *b,int count) {
    double terms[9];for(int i=0;i<count;++i)terms[i]=a[i]*b[i];return compensated(terms,count);
}

static void drivetrain_cross(const double *a,const double *b,double *value) {
    value[0]=a[1]*b[2]-a[2]*b[1];value[1]=a[2]*b[0]-a[0]*b[2];value[2]=a[0]*b[1]-a[1]*b[0];
}

static PyObject *drivetrain_vector(const double *values,int count) {
    PyObject *result=PyTuple_New(count);if(!result)return NULL;
    for(int i=0;i<count;++i){PyObject *item=PyFloat_FromDouble(values[i]);
        if(!item){Py_DECREF(result);return NULL;}PyTuple_SET_ITEM(result,i,item);}
    return result;
}

static PyObject *drivetrain_matrix(const double *values,int rows,int columns,int stride) {
    PyObject *result=PyTuple_New(rows);if(!result)return NULL;
    for(int i=0;i<rows;++i){PyObject *row=drivetrain_vector(values+i*stride,columns);
        if(!row){Py_DECREF(result);return NULL;}PyTuple_SET_ITEM(result,i,row);}
    return result;
}

static int drivetrain_attribute(PyObject *object,const char *name,double *value) {
    PyObject *item=PyObject_GetAttrString(object,name);if(!item)return 0;
    *value=PyFloat_AsDouble(item);Py_DECREF(item);return !PyErr_Occurred();
}

static int drivetrain_attribute_vector(PyObject *object,const char *name,double *values,int count) {
    PyObject *item=PyObject_GetAttrString(object,name);if(!item)return 0;
    int ok=vector(item,values,count);Py_DECREF(item);return ok;
}

static PyObject *drivetrain_prepare(PyObject *self,PyObject *args) {
    PyObject *angular_object,*omega_object,*frames,*config,*inverse_object,*engine_axis_object;
    PyObject *steering_object,*shaft_omega_object,*shaft_inertia_object,*shaft_axis_object;
    PyObject *downstream_object,*downstream_inertias_object,*downstream_axes_object;
    double engine_omega,engine_torque,ratio,dt,engine_inertia,engine_drag;
    if(!PyArg_ParseTuple(args,"OOdOdOdOdOdOdOOOOOO",&angular_object,&omega_object,&engine_omega,&frames,
        &engine_torque,&config,&ratio,&inverse_object,&dt,&engine_axis_object,&engine_inertia,&steering_object,
        &engine_drag,&shaft_omega_object,&shaft_inertia_object,&shaft_axis_object,&downstream_object,
        &downstream_inertias_object,&downstream_axes_object))return NULL;
    int shaft=shaft_omega_object!=Py_None,dimensions=shaft?9:8,wheel_start=shaft?5:4;
    PyObject *rotor_object=PyObject_GetAttrString(config,"wheel_rotor_transport");if(!rotor_object)return NULL;
    int rotor=PyObject_IsTrue(rotor_object);Py_DECREF(rotor_object);if(rotor<0)return NULL;
    if(!PyTuple_Check(downstream_object)){PyErr_SetString(PyExc_ValueError,"实体轴初始速度须为元组");return NULL;}
    int downstream=PyTuple_GET_SIZE(downstream_object)!=0;
    double wheel_inertia,radius,share,final_drive,weights[4],initial[9]={0.};
    if(!drivetrain_attribute(config,"wheel_inertia",&wheel_inertia)
        ||!drivetrain_attribute(config,"wheel_radius",&radius)
        ||!drivetrain_attribute(config,"front_drive_share",&share)
        ||!drivetrain_attribute(config,"final_drive",&final_drive)
        ||!drivetrain_attribute_vector(config,"drive_weights",weights,4)
        ||!vector(angular_object,initial,3)||!vector(omega_object,initial+wheel_start,4))return NULL;
    initial[3]=engine_omega;
    double shaft_inertia=shaft?PyFloat_AsDouble(shaft_inertia_object):1.;
    if(shaft)initial[4]=PyFloat_AsDouble(shaft_omega_object);
    if(PyErr_Occurred())return NULL;
    if(engine_inertia==0.||shaft_inertia==0.||wheel_inertia==0.){
        PyErr_SetString(PyExc_ZeroDivisionError,"机械转子惯量为零");return NULL;}
    double axes[4][3],radii[4],moments_x[4][3],moments_y[4][3],engine_axis[3],shaft_axis[3]={0.};
    double clutch[9]={0.},gear[9]={0.},shaft_gear[9]={0.},engine_gradient[9]={0.};
    double brake[4][9]={0.},longitudinal[4][9]={0.},lateral[4][9]={0.};
    if(!tuple_fields(frames,4)||!vector(engine_axis_object,engine_axis,3)
        ||(shaft&&!vector(shaft_axis_object,shaft_axis,3)))return NULL;
    for(int i=0;i<4;++i){PyObject *frame=PyTuple_GET_ITEM(frames,i);double point[3],tangent[3],axle[3];
        if(!drivetrain_attribute_vector(frame,rotor?"spin_axis":"axle",axes[i],3)
            ||!drivetrain_attribute_vector(frame,"point",point,3)
            ||!drivetrain_attribute_vector(frame,"tangent",tangent,3)
            ||!drivetrain_attribute_vector(frame,"axle",axle,3))return NULL;
        radii[i]=radius;
        if(rotor){if(!drivetrain_attribute(frame,"rolling_radius",&radii[i])
            ||!drivetrain_attribute_vector(frame,"moment_x",moments_x[i],3))return NULL;}
        else {drivetrain_cross(point,tangent,moments_x[i]);
            for(int a=0;a<3;++a)moments_x[i][a]=moments_x[i][a]-radii[i]*axes[i][a];}
        drivetrain_cross(point,axle,moments_y[i]);
        for(int a=0;a<3;++a){brake[i][a]=axes[i][a];longitudinal[i][a]=moments_x[i][a];lateral[i][a]=moments_y[i][a];}
        for(int j=0;j<4;++j){brake[i][wheel_start+j]=(double)(j==i);
            longitudinal[i][wheel_start+j]=j==i?-radii[i]:0.;}
    }
    double wheel_ratios[4],drive_axis[3],terms[9];
    for(int i=0;i<4;++i)wheel_ratios[i]=ratio*weights[i];
    for(int a=0;a<3;++a){engine_gradient[a]=-engine_axis[a];
        if(shaft){for(int i=0;i<4;++i)terms[i]=wheel_ratios[i]*axes[i][a];drive_axis[a]=compensated(terms,4);}
        else if(share==0.)drive_axis[a]=ratio/2*(axes[2][a]+axes[3][a]);
        else {for(int i=0;i<4;++i)terms[i]=weights[i]*axes[i][a];drive_axis[a]=ratio*compensated(terms,4);}
        clutch[a]=shaft?shaft_axis[a]-engine_axis[a]:-engine_axis[a]-drive_axis[a];
        gear[a]=drive_axis[a];shaft_gear[a]=-shaft_axis[a]-drive_axis[a];}
    engine_gradient[3]=clutch[3]=1.;
    if(shaft){clutch[4]=-1.;shaft_gear[4]=1.;}
    for(int i=0;i<4;++i){gear[wheel_start+i]=wheel_ratios[i];
        if(shaft)shaft_gear[wheel_start+i]=-wheel_ratios[i];else clutch[wheel_start+i]=-wheel_ratios[i];}

    MassCoefficients mass={0};mass.dimensions=dimensions;mass.wheel_start=wheel_start;
    mass.engine_inertia=engine_inertia;mass.shaft_inertia=shaft_inertia;mass.wheel_inertia=wheel_inertia;
    if(!matrix_values(inverse_object,mass.inverse,3,3))return NULL;
    double inertias[3]={0.},gradients[3][9]={0.},down_axes[3][3]={0.},old_omega[3]={0.};
    if(downstream){if(!vector(downstream_inertias_object,inertias,3)
        ||!matrix_values(downstream_axes_object,&down_axes[0][0],3,3)||!vector(downstream_object,old_omega,3))return NULL;
        inertias[1]=share>0.?inertias[1]:0.;inertias[2]=share<1.?inertias[2]:0.;
        const double rotor_weights[3][4]={{share/2,share/2,(1-share)/2,(1-share)/2},{.5,.5,0.,0.},{0.,0.,.5,.5}};
        MassCoefficients base=mass;
        for(int i=0;i<3;++i){for(int a=0;a<3;++a){for(int j=0;j<4;++j)terms[j]=rotor_weights[i][j]*axes[j][a];
                gradients[i][a]=down_axes[i][a]+final_drive*compensated(terms,4);}
            for(int j=0;j<4;++j)gradients[i][wheel_start+j]=final_drive*rotor_weights[i][j];
            if(inertias[i]!=0.){int p=mass.projection_count;mass_response_values(&base,gradients[i],mass.responses[p]);
                for(int j=0;j<p;++j){double scale=mass.factors[j]*drivetrain_dot(mass.gradients[j],mass.responses[p],dimensions);
                    for(int a=0;a<dimensions;++a)mass.responses[p][a]=mass.responses[p][a]-scale*mass.responses[j][a];}
                memcpy(mass.gradients[p],gradients[i],dimensions*sizeof(double));
                mass.factors[p]=inertias[i]/(1+inertias[i]*drivetrain_dot(gradients[i],mass.responses[p],dimensions));++mass.projection_count;}}
    }
    mass_response_values(&mass,engine_gradient,mass.engine_response);
    double drag_factor=dt*engine_drag/(1+dt*engine_drag*drivetrain_dot(engine_gradient,mass.engine_response,dimensions));
    double steering[9]={0.},torques[4][3],free_base[9];if(!matrix_values(steering_object,&torques[0][0],4,3))return NULL;
    for(int a=0;a<3;++a){for(int i=0;i<4;++i)terms[i]=torques[i][a];steering[a]=compensated(terms,4);}
    if(downstream){double momentum[9],response[9],steering_response[9],slips[3];
        for(int i=0;i<3;++i)slips[i]=old_omega[i]-drivetrain_dot(gradients[i],initial,dimensions);
        for(int a=0;a<dimensions;++a){for(int i=0;i<3;++i)terms[i]=inertias[i]*gradients[i][a]*slips[i];momentum[a]=compensated(terms,3);}
        mass_response_values(&mass,momentum,response);mass_response_values(&mass,steering,steering_response);
        for(int a=0;a<dimensions;++a)free_base[a]=initial[a]+response[a]+dt*(engine_torque*mass.engine_response[a]+steering_response[a]);
    } else {for(int a=0;a<dimensions;++a)free_base[a]=initial[a]+dt*engine_torque*mass.engine_response[a]
        +(a<3?dt*drivetrain_dot(mass.inverse+3*a,steering,3):0.);}
    double projection=drag_factor*drivetrain_dot(engine_gradient,free_base,dimensions);
    for(int a=0;a<dimensions;++a)free_base[a]=free_base[a]-projection*mass.engine_response[a];
    mass.drag_factor=drag_factor;mass.has_drag=1;

    RotorCoefficients spin={0};spin.dimensions=dimensions;spin.wheel_start=wheel_start;
    spin.rotor=rotor;spin.shaft=shaft;spin.downstream=downstream;spin.engine_inertia=engine_inertia;
    spin.wheel_inertia=wheel_inertia;spin.shaft_inertia=shaft?shaft_inertia:0.;
    memcpy(spin.engine_axis,engine_axis,sizeof(engine_axis));memcpy(spin.wheel_axes,axes,sizeof(axes));
    memcpy(spin.shaft_axis,shaft_axis,sizeof(shaft_axis));memcpy(spin.inertias,inertias,sizeof(inertias));
    for(int i=0;i<3;++i)memcpy(spin.gradients+i*dimensions,gradients[i],dimensions*sizeof(double));
    memcpy(spin.downstream_axes,down_axes,sizeof(down_axes));
    MassCoefficients *mass_copy=PyMem_Malloc(sizeof(mass));RotorCoefficients *spin_copy=PyMem_Malloc(sizeof(spin));
    if(!mass_copy||!spin_copy){PyMem_Free(mass_copy);PyMem_Free(spin_copy);return PyErr_NoMemory();}
    *mass_copy=mass;*spin_copy=spin;
    PyObject *mass_owner=PyCapsule_New(mass_copy,mass_coefficients_name,release_mass_coefficients);
    if(!mass_owner){PyMem_Free(mass_copy);PyMem_Free(spin_copy);return NULL;}
    PyObject *spin_owner=PyCapsule_New(spin_copy,rotor_coefficients_name,release_rotor_coefficients);
    if(!spin_owner){Py_DECREF(mass_owner);PyMem_Free(spin_copy);return NULL;}
    PyObject *items[17]={drivetrain_vector(initial,dimensions),drivetrain_matrix(&axes[0][0],4,3,3),
        drivetrain_vector(radii,4),drivetrain_matrix(&moments_x[0][0],4,3,3),drivetrain_matrix(&moments_y[0][0],4,3,3),
        drivetrain_vector(engine_gradient,dimensions),drivetrain_vector(clutch,dimensions),drivetrain_vector(gear,dimensions),
        shaft?drivetrain_vector(shaft_gear,dimensions):Py_NewRef(Py_None),
        drivetrain_matrix(&brake[0][0],4,dimensions,9),drivetrain_matrix(&longitudinal[0][0],4,dimensions,9),
        drivetrain_matrix(&lateral[0][0],4,dimensions,9),drivetrain_vector(inertias,downstream?3:0),
        drivetrain_matrix(&gradients[0][0],downstream?3:0,dimensions,9),mass_owner,spin_owner,drivetrain_vector(free_base,dimensions)};
    PyObject *result=NULL;int ok=1;for(int i=0;i<17;++i)if(!items[i])ok=0;
    if(ok){result=PyTuple_New(17);if(result)for(int i=0;i<17;++i)PyTuple_SET_ITEM(result,i,items[i]);}
    if(!result)for(int i=0;i<17;++i)Py_XDECREF(items[i]);
    return result;
}
