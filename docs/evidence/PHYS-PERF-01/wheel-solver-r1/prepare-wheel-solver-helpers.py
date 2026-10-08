from pathlib import Path
root=Path(__file__).resolve().parents[3]
folder=root/'logs/physics/PHYS-PERF-01'
path=root/'src/mechanical_kernels.c'
source=path.read_text(encoding='utf-8')
(folder/'wheel-solver-original.c').write_text(source,encoding='utf-8')
(folder/'wheel-solver-original.py').write_bytes((root/'src/tire_drivetrain.py').read_bytes())

# 轮端末状态的原数值体；公共入口和整步求解共用。
start=source.index('static PyObject *wheel_map_state(')
stop=source.index('\n}\n',start)+3
original=source[start:stop]
body=original[original.index('    const double *rx='):original.index('    PyObject *state=PyTuple_New(9);')]
body=body.replace('return NULL;', 'return 0;')
helper='''static int wheel_map_values(WheelMap *packet,int wheel,const double base[9],const double base_velocity[3],
    double fx,double fy,const double active[3],int warm,PyObject *warm_modes,const double tangent[3],const double axle[3],
    double end[9],double velocity[3],double *brake,int *branch_index,int *mode_index) {
    SharedMap *data=packet->shared;
    double free[9],terms[9],values[4];
    for (int a=0;a<9;++a) free[a]=base[a];
    for (int a=0;a<3;++a) velocity[a]=base_velocity[a];
'''+body+'''    *brake=values[3]; *branch_index=selected; *mode_index=port_index;
    return 1;
}
'''
head=original[:original.index('    SharedMap *data=packet->shared;')]
head+='''    double base[9],base_velocity[3],active[3],tangent[3],axle[3],end[9],velocity[3],brake;
    int selected,port_index;
    if (!vector(base_object,base,9) || !vector(velocity_object,base_velocity,3) || !vector(limits_object,active,3)
        || !vector(tangent_object,tangent,3) || !vector(axle_object,axle,3)) return NULL;
    if (!wheel_map_values(packet,wheel,base,base_velocity,fx,fy,active,warm,warm_modes,tangent,axle,
                          end,velocity,&brake,&selected,&port_index)) return NULL;
'''
tail=original[original.index('    PyObject *state=PyTuple_New(9);'):].replace('values[3],selected,port_index','brake,selected,port_index')
source=source[:start]+helper+head+tail+source[stop:]

# 原活动分区导数只从数组读取末状态，Python入口继续发布同样的值。
start=source.index('static PyObject *wheel_map_derivatives(')
stop=source.index('\n}\n',start)+3
original=source[start:stop]
body=original[original.index('    SharedMap *data=packet->shared;'):original.index('    return Py_BuildValue(')]
vector_start=body.index('    double state[9],velocity[3]')
vector_stop=body.index('    for (int a=0; a<3; ++a) terms[a]=velocity[a]*tangent[a];',vector_start)
body=body[:vector_start]+'    double terms[9];\n'+body[vector_stop:]
body=body.replace('    double gradients[2][3];\n','')
body=body.replace('return NULL;','return 0;')
body=body.replace('double vx=compensated(terms,3);','double vx=compensated(terms,3);').replace('double vy=compensated(terms,3);','double vy=compensated(terms,3);')
helper='''static int wheel_derivative_values(WheelMap *packet,int wheel,int branch_index,int port_index,
    const double state[9],const double velocity[3],const double moment_x[3],const double moment_y[3],double radius,
    const double tangent[3],const double axle[3],double speed[2],double slip[2],double gradients[2][3]) {
'''+body+'''    speed[0]=vx; speed[1]=vy; slip[0]=radius*state[wheel+5]-vx; slip[1]=-vy;
    return 1;
}
'''
head=original[:original.index('    SharedMap *data=packet->shared;')]
head+='''    double state[9],velocity[3],moment_x[3],moment_y[3],tangent[3],axle[3],speed[2],slip[2],gradients[2][3];
    if (!vector(state_object,state,9) || !vector(velocity_object,velocity,3)
        || !vector(moment_x_object,moment_x,3) || !vector(moment_y_object,moment_y,3)
        || !vector(tangent_object,tangent,3) || !vector(axle_object,axle,3)) return NULL;
    if (!wheel_derivative_values(packet,wheel,branch_index,port_index,state,velocity,moment_x,moment_y,radius,
                                 tangent,axle,speed,slip,gradients)) return NULL;
'''
tail=original[original.index('    return Py_BuildValue('):]
tail=tail.replace('vx,vy,radius*state[wheel+5]-vx,-vy,','speed[0],speed[1],slip[0],slip[1],')
source=source[:start]+helper+head+tail+source[stop:]

# 接触本构与Jacobian的原算式保持一份实现。
start=source.index('static PyObject *tire_contact_force(');stop=source.index('\n}\n',start)+3
original=source[start:stop]
body=original[original.index('    double impedance='):original.index('    return Py_BuildValue(')]
body=body.replace('    const char *mode;\n','').replace('mode="','*mode="').replace('return NULL;','return 0;')
body=body.replace('    double kappa=patch[0]/denominator,alpha=atan2(-patch[1],denominator);','    *kappa=patch[0]/denominator; *alpha=atan2(-patch[1],denominator);')
body=body.replace('tire_curve_values(kappa,alpha,','tire_curve_values(*kappa,*alpha,')
helper='''static int tire_contact_values(const double force[2],const double previous[2],const double slip[2],
    double denominator,int rolling,double grip,double cx,double cy,double dt,double stiffness,double damping,
    double shape,double curvature,PyObject *hypot_function,double target[2],double deformation[2],double rate[2],
    double patch[2],double *kappa,double *alpha,const char **mode) {
'''+body+'    return 1;\n}\n'
head=original[:original.index('    double impedance=')]
head+='''    double kappa,alpha; const char *mode;
    if (!tire_contact_values(force,previous,slip,denominator,rolling,grip,cx,cy,dt,stiffness,damping,
                             shape,curvature,hypot_function,target,deformation,rate,patch,&kappa,&alpha,&mode)) return NULL;
'''
tail=original[original.index('    return Py_BuildValue('):]
source=source[:start]+helper+head+tail+source[stop:]

start=source.index('static PyObject *tire_contact_jacobian(');stop=source.index('\n}\n',start)+3
original=source[start:stop]
body=original[original.index('    double impedance='):original.index('    return Py_BuildValue("((dd)(dd))",result')]
body=body.replace('return NULL;','return 0;')
helper='''static int tire_jacobian_values(const double force[2],const double previous[2],const double slip[2],
    const double slip_jacobian[4],double denominator,const double denominator_gradient[2],int rolling,
    double grip,double cx,double cy,double dt,double stiffness,double damping,double shape,double curvature,
    PyObject *hypot_function,double result[4]) {
    if (grip==0.) { for (int i=0;i<4;++i) result[i]=0.; return 1; }
'''+body+'    return 1;\n}\n'
head=original[:original.index('    double impedance=')]
head+='''    if (!tire_jacobian_values(force,previous,slip,slip_jacobian,denominator,denominator_gradient,rolling,
                              grip,cx,cy,dt,stiffness,damping,shape,curvature,hypot_function,result)) return NULL;
'''
tail=original[original.index('    return Py_BuildValue("((dd)(dd))",result'):]
source=source[:start]+helper+head+tail+source[stop:]
path.write_text(source,encoding='utf-8')
