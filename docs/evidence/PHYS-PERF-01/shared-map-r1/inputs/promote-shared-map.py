from pathlib import Path
root=Path.cwd();p=root/'src/mechanical_kernels.c';s=p.read_text(encoding='utf-8');block=(root/'logs/physics/PHYS-PERF-01/shared-map-body.c').read_text(encoding='utf-8').replace('(NOdd dii(dddd)(ddd))','(NOdddii(dddd)(ddd))');pos=s.index('static PyMethodDef methods[]');s=s[:pos]+block+'\n'+s[pos:];s=s.replace('static PyMethodDef methods[] = {','static PyMethodDef methods[] = {\n    {"shared_map_coefficients", (PyCFunction)shared_map_coefficients, METH_VARARGS | METH_KEYWORDS, "本共同求解的固定实体轴活动分区"},\n    {"shared_map_state", (PyCFunction)shared_map_state, METH_VARARGS | METH_KEYWORDS, "原九/十一维机械共同末状态映射"},',1);p.write_text(s,encoding='utf-8')
p=root/'src/tire_drivetrain.py';s=p.read_text(encoding='utf-8');s=s.replace('    rotor_known_state,\n','',1);s=s.replace('    rotor_spin_prepared,','    rotor_spin_prepared,\n    shared_map_coefficients,\n    shared_map_state,',1)
marker='    spin_columns = None'
block='''    # 固定机械分区只属于本次advance；法向力、当前轮荷与试探状态逐次传入。
    shared_map = (shared_map_coefficients(mobility_coefficients, spin_coefficients, free_base,
        tuple(branches), (clutch_gradient, shaft_gear_gradient, gear_gradient, brake_gradients[0])
        if hard_gear else (clutch_gradient, shaft_gear_gradient, brake_gradients[0]),
        differential, damping, limits, differential_responses, dt, capacity, efficiency,
        synchronizer_capacity, hard_gear, (radii, rolling_coefficients, config.rolling_transition_speed),
        (ratio, config.front_drive_share, config.final_drive, config.axle_torque_bias_ratios,
         inertias, gradients, tuple(downstream_omega))) if shaft else None)

'''
s=s.replace(marker,block+marker,1)
start=s.index('        def mapped(state):');end=s.index('        variables = dimensions + 2',start)
block='''        def mapped(state):
            nonlocal shared_branch, shared_port_index, road_torques, active_limits
            if shaft:
                end, end_velocity, clutch, loss, gear_reaction, shared_branch, shared_port_index, road_torques, active_limits = (
                    shared_map_state(shared_map, state, loads, tuple(frame.load for frame in frames),
                                     tuple(frame.supported for frame in frames), shared_branch))
                return end, end_velocity, clutch, loss, gear_reaction
            # 八维旧机械对照保留原两端口机制；实体输入轴使用上面的同方程数值块。
            if torque_bias:
                active_limits = bias_limits(state[:dimensions], *state[dimensions:])
            if rolling_active:
                road_torques = rolling_torques(frames,radii,state[wheel_start:],rolling_coefficients,
                                               config.rolling_transition_speed)
            free, end_velocity = known(cross(spin(state), state[:3]), loads)
            order = [shared_branch] + [i for i in range(len(branches)) if i != shared_branch]
            for branch_index in order:
                branch, mc, ml, response, _wheels, _local_response, _plans, _shaft_data = branches[branch_index]
                projected = branch_free(free, branch)
                if ratio:
                    (clutch, loss), _speeds = transmission_state(
                        (dot(clutch_gradient, projected), dot(gear_gradient, projected)),
                        response, dt, capacity, efficiency)
                else:
                    clutch = loss = 0.
                end = tuple(projected[a] - dt * (clutch * mc[a] + loss * ml[a]) for a in range(dimensions))
                if differential_torques(end, branch, differential, damping, active_limits) is not None:
                    shared_branch = branch_index
                    break
            else:
                raise ArithmeticError("限滑/离合共同末状态无可行分区")
            return (end + (0., loss) if torque_bias else end), end_velocity, clutch, loss, 0.

'''
# 旧八维原式含+(0.)，保留这一加法而不做代数删除，以保持其既有舍入/有符号零。
block=block.replace('clutch * mc[a] + loss * ml[a])','clutch * mc[a] + loss * ml[a] + 0.)')
s=s[:start]+block+s[end:];p.write_text(s,encoding='utf-8')
