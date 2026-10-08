/* 原九/十一维共同求根；分区暖状态按每次试探更新，30轮及原精度保持。 */
static double angular_tolerance(double a,double b) {
    double x=fabs(a),y=fabs(b),tol=1e-14;
    double ua=nextafter(x,INFINITY)-x,ub=nextafter(y,INFINITY)-y;
    if (ua>tol) tol=ua;
    if (ub>tol) tol=ub;
    return tol;
}
static double shared_residual_size(const SharedMap *data,const double state[11],const double end[11]) {
    int variables=data->bias ? 11 : 9;
    double maximum=0.;
    for (int a=0; a<variables; ++a) {
        double value=fabs(state[a]-end[a]);
        if (data->bias) value/=a<9 ? angular_tolerance(state[a],end[a]) : PORT_TOLERANCE;
        if (value>maximum) maximum=value;
    }
    return maximum;
}
static PyObject *shared_solution(PyObject *self,PyObject *args) {
    PyObject *coefficients,*guess,*loads,*wheel_loads,*supported,*bias_ports;
    int warm;
    if (!PyArg_ParseTuple(args,"OOOOOiO",&coefficients,&guess,&loads,&wheel_loads,&supported,&warm,&bias_ports)) return NULL;
    SharedMap *data=PyCapsule_GetPointer(coefficients,shared_map_name);
    if (!data) return NULL;
    double state[11],angular[9],normal[9],load[4],support[4];
    if (!vector(guess,state,9) || !tuple_fields(loads,3)
        || !vector(PyTuple_GET_ITEM(loads,0),angular,9) || !vector(wheel_loads,load,4)
        || !vector(supported,support,4)) return NULL;
    PyObject *normal_object=PyTuple_GET_ITEM(loads,1);
    if (!tuple_fields(bias_ports,2) || !PyTuple_Check(normal_object)) {
        if (!PyErr_Occurred()) PyErr_SetString(PyExc_ValueError,"法向载荷须为元组");
        return NULL;
    }
    int suspension=PyTuple_GET_SIZE(normal_object)!=0;
    if (suspension && !vector(normal_object,normal,9)) return NULL;
    double ports[2];
    if (!vector(bias_ports,ports,2)) return NULL;
    if (data->bias) {state[9]=ports[0]; state[10]=ports[1];}
    int variables=data->bias ? 11 : 9,branch_index=warm,port_index=-1;
    double end[11],road[4],active[3],port_values[4],error=0.;
    for (int iteration=0; iteration<30; ++iteration) {
        if (!shared_map_values(data,state,angular,suspension ? normal : NULL,load,support,branch_index,
            end,road,active,port_values,&branch_index,&port_index)) return NULL;
        double residual[11];
        int angular_converged=1,ports_converged=1;
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
            PyObject *result=PyTuple_New(9);
            if (!result) return NULL;
            for (int a=0; a<9; ++a) {
                PyObject *value=PyFloat_FromDouble(end[a]);
                if (!value) {Py_DECREF(result); return NULL;}
                PyTuple_SET_ITEM(result,a,value);
            }
            return Py_BuildValue("(NOdddii(dddd)(ddd)(dd))",result,PyTuple_GET_ITEM(loads,2),
                port_values[0],port_values[2],port_values[1],branch_index,port_index,
                road[0],road[1],road[2],road[3],active[0],active[1],active[2],ports[0],ports[1]);
        }
        if ((data->rolling || data->bias) && iteration>=4) {
            double columns[11][11],matrix[121],rhs[11],rows[121],delta[11],lu_residual[11],correction[11],terms[12],partials[12];
            Py_ssize_t order[11];
            shared_jacobian_values(data,state,load,support,branch_index,port_index,columns);
            for (int a=0; a<variables; ++a) {
                rhs[a]=-residual[a];
                for (int j=0; j<variables; ++j) matrix[a*variables+j]=columns[j][a];
            }
            if (!lu_values(matrix,rhs,variables,rows,order,delta,lu_residual,correction,terms,partials)) return NULL;
            double before=shared_residual_size(data,state,end);
            int accepted=0;
            for (int attempt=0; attempt<8; ++attempt) {
                double candidate[11],target[11],step=ldexp(1.,-attempt);
                for (int a=0; a<variables; ++a) candidate[a]=state[a]+step*delta[a];
                if (!shared_map_values(data,candidate,angular,suspension ? normal : NULL,load,support,branch_index,
                    target,road,active,port_values,&branch_index,&port_index)) return NULL;
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
                if (PyErr_Occurred()) return NULL;
            }
        } else for (int a=0; a<variables; ++a) state[a]=end[a];
    }
    char *number=PyOS_double_to_string(error,'g',6,0,NULL);
    if (!number) return NULL;
    PyErr_Format(PyExc_ArithmeticError,"曲轴/四轮转子共同末状态超过30次迭代：%s",number);
    PyMem_Free(number); return NULL;
}
