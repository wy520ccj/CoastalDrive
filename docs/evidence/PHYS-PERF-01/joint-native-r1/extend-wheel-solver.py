from pathlib import Path

root = Path(__file__).resolve().parents[4]
path = root / 'src/mechanical_kernels.c'
source = path.read_text(encoding='utf-8')
start = source.index('static PyObject *wheel_force_solution(')
body = source.index('    double state[9],end_velocity[3],brake;', start)
end = source.index('\nstatic PyMethodDef methods[]', body)
numerical = source[body:end].replace('context.', 'context->').replace('&context', 'context')
helper = ('static PyObject *wheel_force_result(WheelForce *context,double tolerance,double force[2],int predict) {\n'
          '    double error;\n' + numerical)
wrapper = source[start:body].replace('double tolerance,force[2],error;', 'double tolerance,force[2];')
wrapper += '    return wheel_force_result(&context,tolerance,force,predict);\n}\n'
loaded = r'''
/* 当前跨轮载荷直接进入局部力求根，不装配/读回自由状态元组。 */
static PyObject *loaded_wheel_force_solution(PyObject *self,PyObject *args) {
    WheelForce context;
    PyObject *coefficients,*forces,*velocity,*normal_forces,*normal_responses,*gradients,*gyro_object,*road_object;
    PyObject *active,*moment_x,*moment_y,*previous,*parameters,*hardware,*initial;
    double tolerance,force[2],angular[9],normal[9],gyro[3],road[4];
    int predict;
    if (!PyArg_ParseTuple(args,"Oi" "OOOOOOOOOOOOOOO" "pdOpO",&coefficients,&context.wheel,
        &forces,&velocity,&normal_forces,&normal_responses,&gradients,&gyro_object,&road_object,&active,
        &context.warm_branches,&context.warm_modes,&moment_x,&moment_y,&previous,&parameters,&hardware,
        &context.rolling,&tolerance,&initial,&predict,&context.hypot)) return NULL;
    context.map=PyCapsule_GetPointer(coefficients,wheel_map_name);
    if (!context.map) return NULL;
    if (context.wheel<0 || context.wheel>=4) { PyErr_SetString(PyExc_IndexError,"轮端索引越界"); return NULL; }
    if (!wheel_load_values(&context.map->load,forces,velocity,normal_forces,normal_responses,gradients,context.wheel,
        angular,normal,context.velocity) || !vector(gyro_object,gyro,3)
        || (road_object!=Py_None && !vector(road_object,road,4)) || !vector(active,context.active,3)
        || !vector(moment_x,context.moment_x,3) || !vector(moment_y,context.moment_y,3)
        || !vector(previous,context.previous,2) || !vector(parameters,context.parameters,3)
        || !vector(hardware,context.hardware,5) || !vector(initial,force,2)) return NULL;
    SharedMap *data=context.map->shared;
    known_values(&data->mass,data->base,gyro,angular,normal_forces!=Py_None ? normal : NULL,
        data->dt,road_object!=Py_None ? road : NULL,context.base);
    for (int a=0;a<3;++a) {
        context.tangent[a]=context.map->load.tangents[3*context.wheel+a];
        context.axle[a]=context.map->load.axles[3*context.wheel+a];
    }
    context.radius=data->radii[context.wheel];
    return wheel_force_result(&context,tolerance,force,predict);
}
'''
source = source[:start] + helper + wrapper + loaded + source[end:]
source = source.replace('static PyMethodDef methods[] = {', '''static PyMethodDef methods[] = {
    {"loaded_wheel_force_solution", (PyCFunction)loaded_wheel_force_solution, METH_VARARGS, "当前跨轮自由状态与原轮力求根共入口"},''')
path.write_text(source, encoding='utf-8')
path = root / 'src/tire_drivetrain.py'
source = path.read_text(encoding='utf-8').replace('    wheel_force_solution,', '    loaded_wheel_force_solution,')
start = source.index('    def solve_wheel(i, gyro):')
end = source.index('        rx, ry, _rb = responses[i]', start)
source = source[:start] + '''    def solve_wheel(i, gyro):
        frame, car = frames[i], configurations[i]
        if shaft and car.tire_compliance:
            fx, fy, brake, _error = loaded_wheel_force_solution(wheel_map, i, forces, velocity,
                normal_forces if suspension is not None else None, normal_responses,
                suspension.gradients if suspension is not None else None, gyro,
                road_torques if rolling_active else None, active_limits, warm_branches, warm_modes,
                moments_x[i], moments_y[i], deformations[i], contact_parameters[i], tire_hardware[i],
                rolling[i], .0001, forces[i][:2],
                suspension is not None and sweep == 0 and rolling[i] and wheel_loads[i] > 0, math.hypot)
            return (fx, fy, brake), "magic-formula" if wheel_loads[i] > 0 else "airborne"
        if shaft:
            free_base_wheel, velocity_base = wheel_free_state(wheel_map, forces, velocity,
                normal_forces if suspension is not None else None, normal_responses,
                suspension.gradients if suspension is not None else None, gyro,
                road_torques if rolling_active else None, i)
        else:
            free_base_wheel, velocity_base = known(gyro, load_terms(exclude=i))
''' + source[end:]
path.write_text(source, encoding='utf-8')
