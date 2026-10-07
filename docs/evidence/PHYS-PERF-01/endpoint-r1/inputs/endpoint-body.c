/* 胎冠高度的原割线；同分区代数式与跨分区完整差商保持。 */
static double crown_secant_value(double a0,double a1,double radius,double half_width,double shoulder,double crown) {
    double half=half_width-shoulder,core=radius-shoulder;
    double r0=1-a0*a0,r1=1-a1*a1;
    double b0=sqrt(r0>0. ? r0 : 0.),b1=sqrt(r1>0. ? r1 : 0.);
    int inside0=crown>0. && fabs(a0)*half<2*crown*b0;
    int inside1=crown>0. && fabs(a1)*half<2*crown*b1;
    double radial=b0+b1!=0. ? -(a0+a1)/(b0+b1) : 0.;
    if (inside0 && inside1)
        return core*radial+pow(half,2.)/(4*crown)*((a0+a1)-a0*a0*radial/b0)/b1;
    if (!inside0 && !inside1) {
        double axial=a1!=a0 ? (fabs(a1)-fabs(a0))/(a1-a0) : (a0!=0. ? copysign(1.,a0) : 0.);
        return half*axial+(core-crown)*radial;
    }
    double h0=inside0 ? core*b0+pow(half,2.)*a0*a0/(4*crown*b0) : half*fabs(a0)+(core-crown)*b0;
    double h1=inside1 ? core*b1+pow(half,2.)*a1*a1/(4*crown*b1) : half*fabs(a1)+(core-crown)*b1;
    return (h1-h0)/(a1-a0);
}
static PyObject *crown_extent_secant(PyObject *self,PyObject *args) {
    double a0,a1,radius,half_width,shoulder,crown;
    if (!PyArg_ParseTuple(args,"dddddd",&a0,&a1,&radius,&half_width,&shoulder,&crown)) return NULL;
    return PyFloat_FromDouble(crown_secant_value(a0,a1,radius,half_width,shoulder,crown));
}
static int vector_attribute(PyObject *object,const char *name,double values[3]) {
    PyObject *value=PyObject_GetAttrString(object,name);
    if (!value) return 0;
    int result=vector(value,values); Py_DECREF(value); return result;
}
static int double_attribute(PyObject *object,const char *name,double *value) {
    PyObject *number=PyObject_GetAttrString(object,name);
    if (!number) return 0;
    *value=PyFloat_AsDouble(number); Py_DECREF(number); return !PyErr_Occurred();
}
static void cross_regular(double a[3],double b[3],double result[3]) {
    result[0]=a[1]*b[2]-a[2]*b[1];
    result[1]=a[2]*b[0]-a[0]*b[2];
    result[2]=a[0]*b[1]-a[1]*b[0];
}
/* 查询仍回到原支持面；同平面和跨面分别保留原功共轭公式。 */
static PyObject *cylinder_endpoint(PyObject *self,PyObject *args) {
    PyObject *contact,*hub_end_object,*hub_average_object,*direction_end_object,*direction_average_object;
    PyObject *rotation_axis_object,*velocity_object,*angular_object,*face_difference;
    double angle,scale,dt;
    if (!PyArg_ParseTuple(args,"OOOOOOddOOdO",&contact,&hub_end_object,&hub_average_object,
        &direction_end_object,&direction_average_object,&rotation_axis_object,&angle,&scale,
        &velocity_object,&angular_object,&dt,&face_difference)) return NULL;
    double hub_end[3],hub_average[3],direction_end[3],direction_average[3],rotation_axis[3],velocity[3],angular[3];
    if (!vector(hub_end_object,hub_end) || !vector(hub_average_object,hub_average)
        || !vector(direction_end_object,direction_end) || !vector(direction_average_object,direction_average)
        || !vector(rotation_axis_object,rotation_axis) || !vector(velocity_object,velocity) || !vector(angular_object,angular)) return NULL;
    PyObject *surface=PyObject_GetAttrString(contact,"surface"),*old_normal_object=NULL,*wheel_object=NULL;
    PyObject *found=NULL,*start_object=NULL,*end_object=NULL,*difference_object=NULL;
    double old_axis[3],old_normal[3],old_direction[3],old_hub[3],old_point[3],radius,reach,width,shoulder,crown,old_length;
    if (!surface || !vector_attribute(surface,"wheel_axis",old_axis) || !double_attribute(surface,"wheel_radius",&radius)
        || !double_attribute(surface,"reach",&reach) || !double_attribute(surface,"width",&width)
        || !double_attribute(surface,"shoulder",&shoulder) || !double_attribute(surface,"crown",&crown)
        || !vector_attribute(contact,"direction",old_direction) || !vector_attribute(contact,"hub",old_hub)
        || !vector_attribute(contact,"point",old_point) || !double_attribute(contact,"length",&old_length)) goto failure;
    old_normal_object=PyObject_GetAttrString(contact,"normal");
    if (!old_normal_object || !vector(old_normal_object,old_normal)) goto failure;
    double wheel_axis[3],wheel_average[3],start[3],end[3];
    rotated_path_values(old_axis,rotation_axis,angle,scale,wheel_axis,wheel_average);
    for (int a=0; a<3; ++a) {
        double hub=hub_end[a]+dt*velocity[a];
        start[a]=hub-radius*direction_end[a]; end[a]=hub+reach*direction_end[a];
    }
    wheel_object=Py_BuildValue("(ddd)",wheel_axis[0],wheel_axis[1],wheel_axis[2]);
    start_object=Py_BuildValue("(ddd)",start[0],start[1],start[2]);
    end_object=Py_BuildValue("(ddd)",end[0],end[1],end[2]);
    if (!wheel_object || !start_object || !end_object) goto failure;
    found=PyObject_CallMethod(surface,"relative_entry","OOO",start_object,end_object,wheel_object);
    if (!found) goto failure;
    if (found==Py_None) goto no_contact;
    double normal[3],endpoint[3],fraction=PyFloat_AsDouble(PyTuple_GET_ITEM(found,0));
    if (PyErr_Occurred() || !vector(PyTuple_GET_ITEM(found,1),normal) || !vector(PyTuple_GET_ITEM(found,2),endpoint)) goto failure;
    double length=-radius+fraction*(radius+reach),alignment=-dot(normal,direction_end);
    if (alignment<=0.) goto no_contact;
    int equal=PyObject_RichCompareBool(PyTuple_GET_ITEM(found,1),old_normal_object,Py_EQ);
    if (equal<0) goto failure;
    double change[3];
    for (int a=0; a<3; ++a) change[a]=endpoint[a]-old_point[a];
    double gradient[6];
    if (equal && fabs(dot(normal,change))<=1e-10) {
        double a0=-dot(normal,old_direction),reciprocal=(1/a0+1/alignment)/2;
        double extent=crown_secant_value(dot(normal,old_axis),dot(normal,wheel_axis),radius,width/2,shoulder,crown);
        double p0=a0*old_length;
        for (int a=0; a<3; ++a) change[a]=wheel_axis[a]-old_axis[a];
        double axis_change=dot(normal,change);
        for (int a=0; a<3; ++a) change[a]=dt*velocity[a]+hub_end[a]-old_hub[a];
        double p1=p0+dot(normal,change)-extent*axis_change,arm[3],moment[3];
        for (int a=0; a<3; ++a) arm[a]=reciprocal*(hub_average[a]-extent*wheel_average[a])
                                           +(p0+p1)/(2*a0*alignment)*direction_average[a];
        cross_regular(arm,normal,moment);
        for (int a=0; a<3; ++a) { gradient[a]=reciprocal*normal[a]; gradient[a+3]=moment[a]; }
        alignment=1/reciprocal;
    } else {
        double endpoint_arm[3],old_moment[3],new_moment[3],old_alignment=-dot(old_normal,old_direction);
        for (int a=0; a<3; ++a) endpoint_arm[a]=endpoint[a]-dt*velocity[a];
        cross_regular(old_point,old_normal,old_moment); cross_regular(endpoint_arm,normal,new_moment);
        double speed[6],terms[6];
        for (int a=0; a<3; ++a) {
            gradient[a]=(old_normal[a]/old_alignment+normal[a]/alignment)/2;
            gradient[a+3]=scale*(old_moment[a]/old_alignment+new_moment[a]/alignment)/2;
            speed[a]=velocity[a]; speed[a+3]=angular[a];
        }
        for (int a=0; a<6; ++a) terms[a]=speed[a]*speed[a];
        double squared=sum_values(terms,6);
        if (squared!=0.) {
            double difference;
            PyObject *face=PyTuple_GET_ITEM(found,3);
            if (face!=Py_None) {
                difference_object=PyObject_CallFunction(face_difference,"OOOOOOOddOOd",contact,PyTuple_GET_ITEM(found,1),face,
                    wheel_object,hub_average_object,direction_average_object,rotation_axis_object,angle,scale,
                    velocity_object,angular_object,dt);
                if (!difference_object) goto failure;
                difference=PyFloat_AsDouble(difference_object);
                if (PyErr_Occurred()) goto failure;
            } else difference=length-old_length;
            for (int a=0; a<6; ++a) terms[a]=gradient[a]*speed[a];
            double correction=(difference/dt-sum_values(terms,6))/squared;
            for (int a=0; a<6; ++a) gradient[a]=gradient[a]+correction*speed[a];
        }
    }
    PyObject *result=Py_BuildValue("((dddddd)d)",gradient[0],gradient[1],gradient[2],gradient[3],gradient[4],gradient[5],alignment);
    Py_XDECREF(difference_object); Py_DECREF(found); Py_DECREF(end_object); Py_DECREF(start_object);
    Py_DECREF(wheel_object); Py_DECREF(old_normal_object); Py_DECREF(surface); return result;
no_contact:
    Py_XDECREF(found); Py_XDECREF(end_object); Py_XDECREF(start_object); Py_XDECREF(wheel_object);
    Py_XDECREF(old_normal_object); Py_XDECREF(surface); Py_RETURN_NONE;
failure:
    Py_XDECREF(difference_object); Py_XDECREF(found); Py_XDECREF(end_object); Py_XDECREF(start_object);
    Py_XDECREF(wheel_object); Py_XDECREF(old_normal_object); Py_XDECREF(surface); return NULL;
}
