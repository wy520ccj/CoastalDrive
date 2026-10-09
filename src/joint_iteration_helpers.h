/* 与现行内核同一方程；移除迭代中的Python对象读写和返回装配。 */
static int joint_shared_values(SharedMap *data,double state[11],const double angular[9],
    const double *normal,const double load[4],const double support[4],int warm,double ports[2],double result_state[9],double result_road[4],double result_active[3],double result_ports[4],int *result_branch,int *result_mode) {
    if (data->bias) {state[9]=ports[0]; state[10]=ports[1];}
    int variables=data->bias ? 11 : 9,branch_index=warm,port_index=-1;
    double end[11],road[4],active[3],port_values[4],error=0.,previous_error=INFINITY;
    for (int iteration=0; iteration<30; ++iteration) {
        if (!shared_map_values(data,state,angular,normal,load,support,branch_index,
            end,road,active,port_values,&branch_index,&port_index)) return 0;
        double residual[11];
        int angular_converged=1,ports_converged=1;
        double last_error=error;
        error=0.;
        for (int a=0; a<variables; ++a) {
            residual[a]=state[a]-end[a];
            double magnitude=fabs(residual[a]);
            if (magnitude>error) error=magnitude;
            if (a<9 && !(magnitude<=angular_tolerance(state[a],end[a]))) angular_converged=0;
            if (a>=9 && !(magnitude<=PORT_TOLERANCE)) ports_converged=0;
        }
        if (angular_converged && ports_converged) {
            if (data->bias) {
                ports[0]=port_values[1]; ports[1]=port_values[2];
                shared_active_limits(data,end,active);
                if (!shared_branch_feasible(data,&data->branches[branch_index],end,active)) {
                    for (int a=0; a<variables; ++a) state[a]=end[a];
                    continue;
                }
            }
            memcpy(result_state,end,9*sizeof(double));memcpy(result_road,road,4*sizeof(double));
            memcpy(result_active,active,3*sizeof(double));memcpy(result_ports,port_values,4*sizeof(double));
            *result_branch=branch_index;*result_mode=port_index;return 1;
        }
        /* 固定点已快速下降时沿用原路线；停滞分区提前使用已有解析Newton。 */
        previous_error=iteration ? last_error : INFINITY;
        if ((data->rolling || data->bias) && (iteration>=4 || (iteration>=1 && error>=.2*previous_error))) {
            double columns[11][11],matrix[121],rhs[11],rows[121],delta[11],lu_residual[11],correction[11],terms[12],partials[12];
            Py_ssize_t order[11];
            shared_jacobian_values(data,state,load,support,branch_index,port_index,columns);
            for (int a=0; a<variables; ++a) {
                rhs[a]=-residual[a];
                for (int j=0; j<variables; ++j) matrix[a*variables+j]=columns[j][a];
            }
            if (!lu_values(matrix,rhs,variables,rows,order,delta,lu_residual,correction,terms,partials)) return 0;
            double before=shared_residual_size(data,state,end);
            int accepted=0;
            for (int attempt=0; attempt<8; ++attempt) {
                double candidate[11],target[11],step=ldexp(1.,-attempt);
                for (int a=0; a<variables; ++a) candidate[a]=state[a]+step*delta[a];
                if (!shared_map_values(data,candidate,angular,normal,load,support,branch_index,
                    target,road,active,port_values,&branch_index,&port_index)) return 0;
                if (shared_residual_size(data,candidate,target)<before) {
                    for (int a=0; a<variables; ++a) state[a]=candidate[a];
                    if (data->bias) shared_active_limits(data,state,active);
                    accepted=1; break;
                }
            }
            if (!accepted) {
                for (int a=0; a<variables; ++a) {
                    double pair[2]={state[a],end[a]};
                    state[a]=exact_sum(pair,2,partials)/2;
                }
                if (PyErr_Occurred()) return 0;
            }
        } else for (int a=0; a<variables; ++a) state[a]=end[a];
    }
    char *number=PyOS_double_to_string(error,'g',6,0,NULL);
    if (!number) return 0;
    char message[160];
    PyOS_snprintf(message,sizeof(message),"曲轴/四轮转子共同末状态超过30次迭代：%s",number);
    PyErr_SetString(PyExc_ArithmeticError,message);
    PyMem_Free(number); return 0;
}

static int joint_wheel_map_values(WheelMap *packet,int wheel,const double base[9],const double base_velocity[3],
    double fx,double fy,const double active[3],int warm,int warm_modes[27][4],const double tangent[3],const double axle[3],
    double end[9],double velocity[3],double *brake,int *branch_index,int *mode_index) {
    SharedMap *data=packet->shared;
    double free[9],terms[9],values[4];
    for (int a=0;a<9;++a) free[a]=base[a];
    for (int a=0;a<3;++a) velocity[a]=base_velocity[a];
    const double *rx=packet->load.responses+27*wheel,*ry=rx+9;
    for (int a=0; a<9; ++a) free[a]=free[a]+data->dt*(rx[a]*fx+ry[a]*fy);
    int selected=-1,port_index=-1;
    for (int visit=-1; visit<data->branch_count; ++visit) {
        int index=visit<0 ? warm : visit;
        if (visit>=0 && index==warm) continue;
        SharedBranch *branch=&data->branches[index],*local=&packet->local[4*index+wheel].ports;
        double projected[9];
        shared_branch_free(data,branch,free,active,projected);
        double port_free[4]={0.};
        int n=data->hard ? 4 : 3;
        for (int i=0; i<n; ++i) {
            const double *gradient=i==n-1 ? packet->brake_gradients[wheel] : data->ports[i];
            for (int a=0; a<9; ++a) terms[a]=gradient[a]*projected[a];
            port_free[i]=compensated(terms,9);
        }
        int mode=warm_modes[index][wheel];
        if(!shared_port_state(data,local,port_free,packet->brakes[wheel],mode,values,&port_index))return 0;
        warm_modes[index][wheel]=port_index;
        for (int a=0; a<9; ++a) end[a]=projected[a]-data->dt*(values[0]*branch->mc[a]+values[2]*branch->ml[a]
                                                       +values[3]*local->mc[a]+values[1]*branch->mg[a]);
        int feasible=shared_branch_feasible(data,branch,end,active);
        if (feasible) { selected=index; break; }
    }
    if (selected<0) { PyErr_SetString(PyExc_ArithmeticError,"限滑/离合/制动共同末状态无可行分区"); return 0; }
    for (int a=0; a<3; ++a) velocity[a]=velocity[a]+data->dt/packet->load.mass*(fx*tangent[a]+fy*axle[a]);
    *brake=values[3]; *branch_index=selected; *mode_index=port_index;
    return 1;
}

typedef struct {
    WheelMap *map;int wheel,rolling;
    double base[9],velocity[3],active[3],tangent[3],axle[3],moment_x[3],moment_y[3];
    double radius,previous[2],parameters[3],hardware[5];
    int *warm_branches; int (*warm_modes)[4]; PyObject *hypot;
} JointWheelForce;


static int joint_wheel_force_state(JointWheelForce *data,double fx,double fy,double state[9],double velocity[3],
    double *brake,int *selected,int *mode) {
    int warm=data->warm_branches[data->wheel];
    if (!joint_wheel_map_values(data->map,data->wheel,data->base,data->velocity,fx,fy,data->active,
        warm,data->warm_modes,data->tangent,data->axle,state,velocity,brake,selected,mode)) return 0;
    data->warm_branches[data->wheel]=*selected;
    return 1;
}

static int joint_wheel_force_values(void *context,double fx,double fy,int jacobian,double *result) {
    JointWheelForce *data=context;
    double state[9],velocity[3],brake;
    int selected,mode;
    if (!joint_wheel_force_state(data,fx,fy,state,velocity,&brake,&selected,&mode)) return 0;
    double force[2]={fx,fy},speed[2],slip[2],gradients[2][3];
    if (jacobian) {
        if (!wheel_derivative_values(data->map,data->wheel,selected,mode,state,velocity,data->moment_x,data->moment_y,
            data->radius,data->tangent,data->axle,speed,slip,gradients)) return 0;
    } else {
        wheel_velocity_values(state,velocity,data->wheel+5,data->tangent,data->axle,
            data->moment_x,data->moment_y,data->radius,speed,slip);
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

static int joint_wheel_newton_values(JointWheelForce *data,double tolerance,double force[2],double *final_error) {
    double error=0.;
    for (int iteration=0;iteration<20;++iteration) {
        double residual[2],matrix[4];
        if (!joint_wheel_force_values(data,force[0],force[1],0,residual)
            || !tire_norm(data->hypot,residual[0],residual[1],&error)) return 0;
        if (error<tolerance) { *final_error=error; return 1; }
        if (!joint_wheel_force_values(data,force[0],force[1],1,matrix)) return 0;
        double determinant=matrix[0]*matrix[3]-matrix[1]*matrix[2];
        if (determinant==0.) { PyErr_SetString(PyExc_ZeroDivisionError,"轮胎Jacobian行列式为零"); return 0; }
        double dx=(matrix[3]*residual[0]-matrix[1]*residual[1])/determinant;
        double dy=(matrix[0]*residual[1]-matrix[2]*residual[0])/determinant;
        int exponent;
        for (exponent=0;exponent<12;++exponent) {
            double scale=ldexp(1.,-exponent),candidate_x=force[0]-scale*dx,candidate_y=force[1]-scale*dy;
            double next[2],next_error;
            if (!joint_wheel_force_values(data,candidate_x,candidate_y,0,next) || !tire_norm(data->hypot,next[0],next[1],&next_error)) return 0;
            if (next_error<error) { force[0]=candidate_x; force[1]=candidate_y; break; }
        }
        if (exponent==12) { rolling_root_failure("轮胎隐式积分不收敛：残差 ",error); return 0; }
    }
    rolling_root_failure("轮胎隐式积分超过20次迭代：残差 ",error); return 0;
}

static int joint_wheel_force_result(JointWheelForce *context,double tolerance,double force[2],int predict,double *result_brake) {
    double error;
    double state[9],end_velocity[3],brake;
    int selected,mode;
    if (predict) {
        /* 首轮真实轮荷刷新后的同方程零滑移切线初值。 */
        double speed[2],slip[2],gradients[2][3],slopes[2],patch[2],matrix[4];
        if (!joint_wheel_force_state(context,0.,0.,state,end_velocity,&brake,&selected,&mode)
            || !wheel_derivative_values(context->map,context->wheel,selected,mode,state,end_velocity,
                context->moment_x,context->moment_y,context->radius,context->tangent,context->axle,speed,slip,gradients)) return 0;
        double dt=context->map->shared->dt,impedance=context->hardware[1]*dt+context->hardware[2];
        double denominator=fabs(speed[0])>context->hardware[0] ? fabs(speed[0]) : context->hardware[0];
        for (int a=0;a<2;++a) {
            slopes[a]=context->parameters[a+1]/denominator;
            patch[a]=slip[a]+context->hardware[1]*context->previous[a]/impedance;
            for (int b=0;b<2;++b) matrix[2*a+b]=(double)(a==b)-slopes[a]*(gradients[b][a]-(double)(a==b)/impedance);
        }
        double rhs_x=slopes[0]*patch[0],rhs_y=slopes[1]*patch[1];
        double determinant=matrix[0]*matrix[3]-matrix[1]*matrix[2];
        if (determinant==0.) { PyErr_SetString(PyExc_ZeroDivisionError,"轮胎初值切线行列式为零"); return 0; }
        force[0]=(matrix[3]*rhs_x-matrix[1]*rhs_y)/determinant;
        force[1]=(matrix[0]*rhs_y-matrix[2]*rhs_x)/determinant;
    }
    int solved=context->rolling ? rolling_root_values(joint_wheel_force_values,context,context->parameters[0],tolerance,force,context->hypot,&error)
                               : joint_wheel_newton_values(context,tolerance,force,&error);
    if (!solved) return 0;
    if (!joint_wheel_force_state(context,force[0],force[1],state,end_velocity,&brake,&selected,&mode)) return 0;
    *result_brake=brake;return 1;
}

static int joint_brake_values(WheelMap *packet,const double state[9],double forces[4][3],int branch_index,int port_index) {
    SharedMap *data=packet->shared;
    if (branch_index<0 || branch_index>=data->branch_count) {
        PyErr_SetString(PyExc_IndexError,"制动修正分区索引越界"); return 0;
    }
    SharedBranch *branch=&data->branches[branch_index];
    if (port_index<0 || port_index>=branch->plan_count) {
        PyErr_SetString(PyExc_IndexError,"制动修正端口索引越界"); return 0;
    }
    SharedPortPlan *plan=&branch->plans[port_index];
    double corrections[4][9],rows[4][5],terms[9];
    for (int wheel=0;wheel<4;++wheel) {
        const double *rb=packet->local[4*branch_index+wheel].ports.mc;
        double direction[4],rhs[3],output[3],dc,dg,dl;
        int n=data->hard ? 4 : 3;
        for (int i=0;i<n;++i) {
            const double *gradient=i==n-1 ? packet->brake_gradients[0] : data->ports[i];
            for (int a=0;a<9;++a) terms[a]=gradient[a]*rb[a];
            direction[i]=compensated(terms,9);
        }
        if (data->hard) {
            const int ports[3]={0,2,3};
            double gear_free=direction[1]/branch->port_response[1][1],reduced[3];
            for (int i=0;i<3;++i)
                reduced[i]=direction[ports[i]]-branch->port_response[ports[i]][1]*gear_free;
            rhs[0]=plan->modes[0]==0. ? reduced[0] : 0.;
            rhs[1]=plan->modes[1]==0. ? reduced[1] : plan->slope*gear_free;
            rhs[2]=plan->modes[2]==0. ? reduced[2] : 0.;
            for (int i=0;i<3;++i) {
                for (int j=0;j<3;++j) terms[j]=plan->columns[j][i]*rhs[j];
                output[i]=compensated(terms,3);
            }
            dc=output[0]; dl=output[1];
            for (int j=0;j<3;++j)
                terms[j]=branch->port_response[1][ports[j]]*output[j]/branch->port_response[1][1];
            dg=gear_free-compensated(terms,3);
        } else {
            for (int i=0;i<3;++i) rhs[i]=plan->modes[i]==0. ? direction[i] : 0.;
            for (int i=0;i<3;++i) {
                for (int j=0;j<3;++j) terms[j]=plan->columns[j][i]*rhs[j];
                output[i]=compensated(terms,3);
            }
            dc=output[0]; dg=output[1]; dl=0.;
        }
        for (int a=0;a<9;++a)
            corrections[wheel][a]=rb[a]-dc*branch->mc[a]-dg*branch->mg[a]-dl*branch->ml[a];
    }
    double largest=0.;
    for (int i=0;i<4;++i) {
        const double *gradient=packet->brake_gradients[i],*response=packet->load.responses+27*i+18;
        for (int a=0;a<9;++a) terms[a]=gradient[a]*state[a];
        double speed=compensated(terms,9);
        for (int a=0;a<9;++a) terms[a]=gradient[a]*response[a];
        double diagonal=compensated(terms,9);
        double demand=forces[i][2]+speed/(data->dt*diagonal);
        if (fabs(demand)<packet->brakes[i]) {
            for (int j=0;j<4;++j) {
                for (int a=0;a<9;++a) terms[a]=gradient[a]*corrections[j][a];
                rows[i][j]=compensated(terms,9);
            }
            rows[i][4]=speed/data->dt;
        } else {
            double target=demand<packet->brakes[i] ? demand : packet->brakes[i];
            if (target < -packet->brakes[i]) target=-packet->brakes[i];
            for (int j=0;j<4;++j) rows[i][j]=(double)(i==j);
            rows[i][4]=target-forces[i][2];
        }
        for (int j=0;j<4;++j) if (fabs(rows[i][j])>largest) largest=fabs(rows[i][j]);
    }
    double rounding=16*(nextafter(largest,INFINITY)-largest);
    int pivot_rows[4],pivot_columns[4],row=0;
    for (int column=0;column<4;++column) {
        int pivot=row;
        for (int i=row+1;i<4;++i) if (fabs(rows[i][column])>fabs(rows[pivot][column])) pivot=i;
        if (fabs(rows[pivot][column])<=rounding) continue;
        for (int j=0;j<5;++j) {
            double value=rows[row][j]; rows[row][j]=rows[pivot][j]; rows[pivot][j]=value;
        }
        double scale=rows[row][column];
        for (int j=0;j<5;++j) rows[row][j]=rows[row][j]/scale;
        for (int i=0;i<4;++i) if (i!=row) {
            double factor=rows[i][column];
            for (int j=0;j<5;++j) rows[i][j]=rows[i][j]-factor*rows[row][j];
        }
        pivot_rows[row]=row; pivot_columns[row]=column;
        if (++row==4) break;
    }
    double delta[4]={0.};
    for (int i=0;i<row;++i) delta[pivot_columns[i]]=rows[pivot_rows[i]][4];
    for(int i=0;i<4;++i)forces[i][2]+=delta[i];return 1;
}
