"""提取共同映射/解析导数数值函数；将原实体轴求根控制流移到同一C块。"""
import subprocess
from pathlib import Path
root=Path.cwd();folder=root/'logs/physics/PHYS-PERF-01'
path=root/'src/mechanical_kernels.c';source=path.read_text(encoding='utf-8')
begin=source.index('    for (int i=0; i<3; ++i) active[i]=data->limits[i];',source.index('static PyObject *shared_map_state'))
active_end=source.index('    if (data->rolling)',begin)
active=source[begin:active_end]
active_helper='static void shared_active_limits(const SharedMap *data,const double state[11],double active[3]) {\n'+active+'}\n\n'
end=source.index('    PyObject *result=PyTuple_New(data->bias ? 11 : 9);',active_end)
body=source[active_end:end].replace('return NULL;','return 0;')
helper='''static int shared_map_values(const SharedMap *data,const double state[11],const double angular[9],
    const double *normal,const double load[4],const double support[4],int warm,double output[11],
    double road[4],double active[3],double port_values[4],int *branch_output,int *port_output) {
    double momentum[3],gyro[3],free[9],terms[9],end[9];
    int suspension=normal!=NULL;
    for (int i=0; i<4; ++i) {road[i]=0.; port_values[i]=0.;}
    shared_active_limits(data,state,active);
'''+body+'''    for (int a=0; a<(data->bias ? 11 : 9); ++a) output[a]=a<9 ? end[a] : port_values[a==9 ? 1 : 2];
    *branch_output=branch_index; *port_output=port_index;
    return 1;
}

'''
source=source[:begin]+'''    int branch_index,port_index;
    if (!shared_map_values(data,state,angular,suspension ? normal : NULL,load,support,warm,
        end,road,active,port_values,&branch_index,&port_index)) return NULL;
'''+source[end:]
source=source.replace('double active[3],road[4]={0.},end[9],port_values[4]={0.};','double active[3],road[4],end[11],port_values[4];',1)
source=source.replace('double state[11],angular[9],normal[9],load[4],support[4],momentum[3],gyro[3],free[9],terms[9];','double state[11],angular[9],normal[9],load[4],support[4];',1)
source=source.replace('static PyObject *shared_map_state(',active_helper+helper+'static PyObject *shared_map_state(',1)
# 解析导数仍共享同一算式和列次序，公开入口只保留参数读取与装配。
method_begin=source.index('static PyObject *shared_map_jacobian(')
numeric_begin=source.index('    rotor_spin_values(&data->spin,state,current_spin);',method_begin)
numeric_end=source.index('    return columns;\n}',numeric_begin)
body=source[numeric_begin:numeric_end]
body=body.replace('    PyObject *columns=PyList_New(variables);\n    if (!columns) return NULL;\n','')
body=body.replace('''        PyObject *column=PyTuple_New(variables);
        if (!column) { Py_DECREF(columns); return NULL; }
''','')
body=body.replace('''            PyObject *number=PyFloat_FromDouble((double)(a==j)-end_column);
            if (!number) { Py_DECREF(column); Py_DECREF(columns); return NULL; }
            PyTuple_SET_ITEM(column,a,number);''','''            columns[j][a]=(double)(a==j)-end_column;''')
body=body.replace('        PyList_SET_ITEM(columns,j,column);\n','')
jac_helper='''static void shared_jacobian_values(const SharedMap *data,const double state[11],const double load[4],
    const double support[4],int branch_index,int port_index,double columns[11][11]) {
    const SharedBranch *branch=&data->branches[branch_index];
    const SharedPortPlan *plan=&branch->plans[port_index];
    int variables=data->bias ? 11 : 9;
    double current_spin[3],derivatives[3][11]={{0.}},terms[9];
'''+body+'}\n\n'
public='''    double numeric[11][11];
    shared_jacobian_values(data,state,load,support,branch_index,port_index,numeric);
    PyObject *columns=PyList_New(variables);
    if (!columns) return NULL;
    for (int j=0; j<variables; ++j) {
        PyObject *column=PyTuple_New(variables);
        if (!column) {Py_DECREF(columns); return NULL;}
        for (int a=0; a<variables; ++a) {
            PyObject *value=PyFloat_FromDouble(numeric[j][a]);
            if (!value) {Py_DECREF(column); Py_DECREF(columns); return NULL;}
            PyTuple_SET_ITEM(column,a,value);
        }
        PyList_SET_ITEM(columns,j,column);
    }
'''
source=source[:numeric_begin]+public+source[numeric_end:]
source=source.replace('    const SharedPortPlan *plan=&branch->plans[port_index];\n    int variables=data->bias ? 11 : 9;\n    double state[11],load[4],support[4],current_spin[3],derivatives[3][11]={{0.}},terms[9];',
    '    int variables=data->bias ? 11 : 9;\n    double state[11],load[4],support[4];',1)
source=source.replace('static PyObject *shared_map_jacobian(',jac_helper+'static PyObject *shared_map_jacobian(',1)
index=source.index('static PyMethodDef methods[]')
source=source[:index]+(folder/'shared-solution-body.c').read_text(encoding='utf-8')+'\n'+source[index:]
source=source.replace('static PyMethodDef methods[] = {','static PyMethodDef methods[] = {\n    {"shared_solution", (PyCFunction)shared_solution, METH_VARARGS, "原九/十一维共同转子求根"},',1)
path.write_text(source,encoding='utf-8')
path=root/'src/tire_drivetrain.py'
source=subprocess.check_output(['git','show','127c1d0:src/tire_drivetrain.py'],text=True,encoding='utf-8')
source=source.replace('    shared_map_state,','    shared_map_state,\n    shared_solution,',1)
marker='''        loads = load_terms()
        def mapped(state):'''
replacement='''        loads = load_terms()
        if shaft:
            end, end_velocity, clutch, loss, gear_reaction, shared_branch, shared_port_index, road_torques, active_limits, bias_ports = shared_solution(
                shared_map, guess, loads, tuple(frame.load for frame in frames),
                tuple(frame.supported for frame in frames), shared_branch, bias_ports)
            return end, end_velocity, clutch, loss, gear_reaction
        def mapped(state):'''
assert source.count(marker)==1
source=source.replace(marker,replacement)
# 初版保留旧八维代码的原控制流，先做完整逐调用核对。
path.write_text(source,encoding='utf-8')
