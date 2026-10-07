from pathlib import Path

root = Path.cwd()
p = root / 'src/mechanical_kernels.c'
s = p.read_text(encoding='utf-8')
s = s.replace('const SharedBranch *branch,const double free[4],\n                             double values[4],int *index)', 'const SharedBranch *branch,const double free[4],\n                             double brake_capacity,int warm,double values[4],int *index)', 1)
s = s.replace('    for (int k=0; k<branch->plan_count; ++k) {\n        const SharedPortPlan *plan=&branch->plans[k];', '    for (int visit=-1; visit<branch->plan_count; ++visit) {\n        int k=visit<0 ? warm : visit;\n        if (k<0 || (visit>=0 && k==warm)) continue;\n        const SharedPortPlan *plan=&branch->plans[k];', 1)
s = s.replace('data->dt,data->capacity,0.,data->efficiency,', 'data->dt,data->capacity,brake_capacity,data->efficiency,', 1)
s = s.replace('double capacities[3]={data->capacity,data->synchronizer,0.}', 'double capacities[3]={data->capacity,data->synchronizer,brake_capacity}', 1)
s = s.replace('shared_port_state(data,branch,port_free,port_values,&port_index)', 'shared_port_state(data,branch,port_free,0.,-1,port_values,&port_index)', 1)
block = (root / 'logs/physics/PHYS-PERF-01/wheel-map-body.c').read_text(encoding='utf-8')
s = s.replace('static PyMethodDef methods[] = {', block + '\nstatic PyMethodDef methods[] = {\n    {"wheel_map_coefficients", (PyCFunction)wheel_map_coefficients, METH_VARARGS, "本子步轮胎局部端口的固定系数"},\n    {"wheel_map_state", (PyCFunction)wheel_map_state, METH_VARARGS, "原轮胎试探力与传动制动共同末状态"},', 1)
p.write_text(s, encoding='utf-8')
p = root / 'src/tire_drivetrain.py'
s = p.read_text(encoding='utf-8').replace('    wheel_load_prepared,', '    wheel_load_prepared,\n    wheel_map_coefficients,\n    wheel_map_state,', 1)
marker = '    def shared_jacobian_columns(state):'
s = s.replace(marker, '    wheel_map = (wheel_map_coefficients(shared_map, wheel_coefficients, tuple(branches),\n                                          brake_gradients, brakes) if shaft else None)\n\n' + marker, 1)
marker = '        def local_state(fx, fy):\n'
s = s.replace(marker, marker + '            if shaft:\n                end, velocity_end, brake, partition = wheel_map_state(\n                    wheel_map, i, free_base_wheel, velocity_base, fx, fy, active_limits,\n                    warm_branches[i], warm_modes, frame.tangent, frame.axle)\n                warm_branches[i] = partition[0]\n                return end, velocity_end, brake, partition\n', 1)
p.write_text(s, encoding='utf-8')
