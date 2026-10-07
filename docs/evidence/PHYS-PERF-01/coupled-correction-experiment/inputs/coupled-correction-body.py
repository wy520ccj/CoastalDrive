    def correct_coupled(guess, velocity_guess):
        """同一末状态联立六维车身速度与八个接触区力；不提交中间冲量。"""
        nonlocal suspension, normal_forces, frames
        original_system, original_normal, original_frames = suspension, normal_forces, frames
        original_forces = tuple(forces)
        values = tuple(velocity_guess) + tuple(guess[:3]) + tuple(value for wheel in forces for value in wheel[:2])
        force_scale = dt / mass

        def residual(values):
            nonlocal suspension, normal_forces
            suspension = finite_contact_system(reference_suspension, values[:3], values[3:6], dt)
            normal_projection()
            normal_forces = shared_suspension(suspension, values[:3], values[3:6], dt).axial_force
            normal_loads()
            for i in range(4):
                forces[i] = (*values[6 + 2 * i:8 + 2 * i], original_forces[i][2])
            state, end_velocity, _clutch, _loss, _gear = shared(tuple(values[3:6]) + tuple(guess[3:]))
            errors = tuple(values[a] - end for a, end in enumerate(tuple(end_velocity) + tuple(state[:3])))
            for i in range(4):
                fx, fy, _brake = forces[i]
                target, _details = contact(i, state, end_velocity, fx, fy)
                errors += (force_scale * (fx - target[0]), force_scale * (fy - target[1]))
            return errors

        errors = residual(values)
        columns = []
        for j in range(14):
            plus, minus = list(values), list(values)
            step = math.ulp(1.) ** (1 / 3) * max(1., abs(values[j]))
            plus[j] += step
            minus[j] -= step
            high, low = residual(plus), residual(minus)
            columns.append(tuple((high[a] - low[a]) / (plus[j] - minus[j]) for a in range(14)))
        delta = _solve(tuple(tuple(columns[j][a] for j in range(14)) for a in range(14)),
                       tuple(-value for value in errors))
        before = max(abs(value) for value in errors)
        for attempt in range(8):
            candidate = tuple(values[i] + 2.**-attempt * delta[i] for i in range(14))
            after = residual(candidate)
            if max(abs(value) for value in after) < before:
                return
        suspension, normal_forces, frames = original_system, original_normal, original_frames
        forces[:] = original_forces
        normal_projection()

