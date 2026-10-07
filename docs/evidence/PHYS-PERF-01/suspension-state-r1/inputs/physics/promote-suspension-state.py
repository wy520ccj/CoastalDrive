"""提取原LU数值函数，移植原四轮活动集；能量账留在原Python入口。"""
from pathlib import Path
root=Path.cwd()
path=root/'src/mechanical_kernels.c'
source=path.read_text(encoding='utf-8')
begin=source.index('    for (Py_ssize_t col=0; col<n; ++col) {', source.index('static PyObject *solve_lu'))
end=source.index('    PyObject *output=PyTuple_New(n);',begin)
block=source[begin:end].replace('goto failed;', 'return 0;')
helper='''/* 公开LU与四轮活动集共用原消元、fsum及一次残差修正。 */
static int lu_values(const double *original,const double *rhs,Py_ssize_t n,
                     double *rows,Py_ssize_t *order,double *result,double *residual,
                     double *correction,double *terms,double *partials) {
    for (Py_ssize_t i=0; i<n; ++i) {
        order[i]=i;
        for (Py_ssize_t j=0; j<n; ++j) rows[i*n+j]=original[i*n+j];
    }
'''+block+'''    for (Py_ssize_t i=0; i<n; ++i) result[i]=result[i]+correction[i];
    return 1;
}

'''
source=source[:begin]+'''    if (!lu_values(original,rhs,n,rows,order,result,residual,correction,terms,partials)) goto failed;
'''+source[end:]
source=source.replace('PyFloat_FromDouble(result[i]+correction[i])','PyFloat_FromDouble(result[i])')
source=source.replace('static PyObject *solve_lu(',helper+'static PyObject *solve_lu(',1)
source=source.replace('''        order[i]=i;
        for (Py_ssize_t j=0; j<n; ++j) rows[i*n+j]=original[i*n+j];
    }
    if (!lu_values''','''    }
    if (!lu_values''',1)
kernel=r'''
/* 原四轮接触/阻尼/止挡活动集；分区次序、64轮与精度保持。 */
static PyObject *suspension_contact_state(PyObject *self,PyObject *args) {
    PyObject *compression_object,*speed_object,*mobility_object,*touching_object,*stiffness_object;
    PyObject *compression_damping_object,*extension_damping_object,*stops_object,*geometry_object;
    double travel,dt;
    if (!PyArg_ParseTuple(args,"OOOOOOOOddO",&compression_object,&speed_object,&mobility_object,
        &touching_object,&stiffness_object,&compression_damping_object,&extension_damping_object,
        &stops_object,&travel,&dt,&geometry_object)) return NULL;
    double compression[4],speed[4],mobility[16],touching[4],stiffness[16],cd[4],ed[4],stops[4],geometry[4];
    if (!vector(compression_object,compression,4) || !vector(speed_object,speed,4)
        || !matrix_values(mobility_object,mobility,4,4) || !vector(touching_object,touching,4)
        || !matrix_values(stiffness_object,stiffness,4,4) || !vector(compression_damping_object,cd,4)
        || !vector(extension_damping_object,ed,4) || !vector(stops_object,stops,4)
        || !vector(geometry_object,geometry,4)) return NULL;
    double damping[4],bound[4],end[4],forces[4],raw[4],terms[9],partials[9];
    int modes[4],stop_modes[4],zero_mobility=1,converged=0;
    for (int i=0; i<16; ++i) if (mobility[i]!=0.) zero_mobility=0;
    for (int i=0; i<4; ++i) {
        modes[i]=touching[i]!=0.; damping[i]=speed[i]<0. ? cd[i] : ed[i];
        stop_modes[i]=compression[i]>travel ? 1 : compression[i]<-travel ? -1 : 0;
        bound[i]=stop_modes[i]*travel;
    }
    for (int iteration=0; iteration<64; ++iteration) {
        double system[16],rhs[4],equations[64]={0.},values[8],rows[64],solution[8],residual[8],correction[8];
        Py_ssize_t order[8];
        for (int i=0; i<16; ++i) system[i]=stiffness[i];
        for (int i=0; i<4; ++i) {
            system[4*i+i]+=damping[i]/dt+(stop_modes[i] ? stops[i] : 0.);
            rhs[i]=damping[i]*compression[i]/dt+(stop_modes[i] ? stops[i]*bound[i] : 0.);
            for (int j=0; j<4; ++j) {
                if (!modes[i]) {
                    equations[(2*i)*8+j]=system[i*4+j];
                    equations[(2*i+1)*8+j+4]=(double)(i==j);
                } else {
                    equations[(2*i)*8+j]=(double)(i==j);
                    equations[(2*i)*8+j+4]=dt*dt*mobility[i*4+j];
                    equations[(2*i+1)*8+j]=-system[i*4+j];
                    equations[(2*i+1)*8+j+4]=(double)(i==j);
                }
            }
            values[2*i]=modes[i] ? geometry[i]-dt*speed[i] : rhs[i];
            values[2*i+1]=modes[i] ? -rhs[i] : 0.;
        }
        if (!lu_values(equations,values,8,rows,order,solution,residual,correction,terms,partials)) return NULL;
        for (int i=0; i<4; ++i) {end[i]=solution[i]; forces[i]=solution[i+4];}
        int next_modes[4],next_stops[4],same=1;
        double next_damping[4];
        for (int i=0; i<4; ++i) {
            for (int j=0; j<4; ++j) terms[j]=stiffness[i*4+j]*end[j];
            terms[4]=damping[i]*(end[i]-compression[i])/dt;
            terms[5]=stop_modes[i] ? stops[i]*(end[i]-bound[i]) : 0.;
            raw[i]=exact_sum(terms,6,partials);
            for (int j=0; j<4; ++j) terms[j]=mobility[i*4+j]*forces[j];
            double target=geometry[i]-dt*speed[i]-dt*dt*compensated(terms,4);
            next_modes[i]=modes[i];
            if (!modes[i] && touching[i]!=0. && end[i]<target-1e-10) next_modes[i]=1;
            else if (modes[i] && forces[i]<-1e-7) next_modes[i]=0;
            next_damping[i]=end[i]>=compression[i] ? cd[i] : ed[i];
            next_stops[i]=end[i]>travel ? 1 : end[i]<-travel ? -1 : 0;
            if (next_modes[i]!=modes[i] || next_damping[i]!=damping[i] || next_stops[i]!=stop_modes[i]) same=0;
        }
        if (PyErr_Occurred()) return NULL;
        if (same) {
            if (zero_mobility) for (int i=0; i<4; ++i) {
                if (modes[i]) {
                    for (int j=0; j<4; ++j) {
                        double k=stiffness[i*4+j];
                        terms[j]=modes[j] ? fma(-k*dt,speed[j],k*geometry[j]) : k*end[j];
                    }
                    terms[4]=fma(-damping[i],speed[i],damping[i]*(geometry[i]-compression[i])/dt);
                    terms[5]=stop_modes[i] ? fma(-stops[i]*dt,speed[i],stops[i]*(geometry[i]-bound[i])) : 0.;
                    raw[i]=exact_sum(terms,6,partials);
                }
                forces[i]=modes[i] ? raw[i] : 0.;
            }
            converged=1; break;
        }
        for (int i=0; i<4; ++i) {
            modes[i]=next_modes[i]; damping[i]=next_damping[i]; stop_modes[i]=next_stops[i]; bound[i]=stop_modes[i]*travel;
        }
    }
    if (PyErr_Occurred()) return NULL;
    if (!converged) {PyErr_SetString(PyExc_ArithmeticError,"悬架接触/阻尼/止挡活动集未收敛"); return NULL;}
    return Py_BuildValue("((dddd)(dddd)(dddd)(dddd))",end[0],end[1],end[2],end[3],
        forces[0],forces[1],forces[2],forces[3],raw[0],raw[1],raw[2],raw[3],
        damping[0],damping[1],damping[2],damping[3]);
}

'''
index=source.index('static PyMethodDef methods[]')
source=source[:index]+kernel+source[index:]
source=source.replace('static PyMethodDef methods[] = {','static PyMethodDef methods[] = {\n    {"suspension_contact_state", (PyCFunction)suspension_contact_state, METH_VARARGS, "原四轮接触阻尼止挡活动集"},',1)
path.write_text(source,encoding='utf-8')
path=root/'src/suspension.py'
source=path.read_text(encoding='utf-8').replace('from mechanical_kernels import dot','from mechanical_kernels import dot, suspension_contact_state',1)
begin=source.index('    modes = [1 if contact else 0 for contact in touching]')
end=source.index('    delta = tuple(end[i] - compression[i] for i in range(4))',begin)
source=source[:begin]+'''    end, forces, raw, damping = suspension_contact_state(
        compression, extension_speed, mobility, touching, stiffness,
        compression_damping, extension_damping, stops, travel, dt, geometry)
'''+source[end:]
path.write_text(source,encoding='utf-8')
