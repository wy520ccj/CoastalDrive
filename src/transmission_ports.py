"""有限离合、双向齿轮损失与单轮制动的共同末状态约束。"""

from rotor_dynamics import cross, dot

PORT_TOLERANCE = 1e-11


def gear_loss_limits(clutch, efficiency):
    """损失转矩按输入轴折算；静止允许区间反力，运动时损失功非负。"""
    if clutch >= 0:
        return (1 - 1 / efficiency) * clutch, (1 - efficiency) * clutch
    return (1 - efficiency) * clutch, (1 - 1 / efficiency) * clutch


def transmission_state(free, response, dt, capacity, efficiency):
    """解两端口；free=(离合滑差, 齿轮输入速)，response为同一机械逆惯量。"""
    slip_free, speed_free = free
    dcc, dcl = response[0]
    _dcl, dll = response[1]
    tolerance = PORT_TOLERANCE

    def feasible(clutch, loss, clutch_mode, gear_mode):
        slip = slip_free - dt * (dcc * clutch + dcl * loss)
        speed = speed_free - dt * (dcl * clutch + dll * loss)
        low, high = gear_loss_limits(clutch, efficiency)
        if abs(clutch) > capacity + tolerance or not low - tolerance <= loss <= high + tolerance:
            return None
        if clutch_mode == "locked" and abs(slip) > tolerance:
            return None
        if clutch_mode == "positive-slip" and slip < -tolerance:
            return None
        if clutch_mode == "negative-slip" and slip > tolerance:
            return None
        if gear_mode == "static" and abs(speed) > tolerance:
            return None
        if gear_mode == "positive-motion" and (speed < -tolerance or abs(loss - high) > tolerance):
            return None
        if gear_mode == "negative-motion" and (speed > tolerance or abs(loss - low) > tolerance):
            return None
        return (clutch, loss), (slip, speed)

    for direction in (-1, 1):
        gear_mode = "positive-motion" if direction > 0 else "negative-motion"
        for sign in (-1, 1):
            slope = 1 - efficiency if direction * sign > 0 else 1 - 1 / efficiency
            clutch = slip_free / (dt * (dcc + dcl * slope))
            if clutch * sign >= -tolerance:
                result = feasible(clutch, slope * clutch, "locked", gear_mode)
                if result is not None:
                    return result
            clutch = sign * capacity
            mode = "positive-slip" if sign > 0 else "negative-slip"
            result = feasible(clutch, slope * clutch, mode, gear_mode)
            if result is not None:
                return result

    determinant = dcc * dll - dcl * dcl
    clutch = (dll * slip_free - dcl * speed_free) / (dt * determinant)
    loss = (dcc * speed_free - dcl * slip_free) / (dt * determinant)
    result = feasible(clutch, loss, "locked", "static")
    if result is not None:
        return result
    for sign in (-1, 1):
        clutch = sign * capacity
        loss = (speed_free / dt - dcl * clutch) / dll
        mode = "positive-slip" if sign > 0 else "negative-slip"
        result = feasible(clutch, loss, mode, "static")
        if result is not None:
            return result
    raise ArithmeticError("离合/齿轮共同末状态无可行解")


def _inverse_three(rows):
    cofactors = cross(rows[1], rows[2]), cross(rows[2], rows[0]), cross(rows[0], rows[1])
    determinant = dot(rows[0], cofactors[0])
    return tuple(tuple(sum(cofactors[j][i] * float(j == k) for j in range(3)) / determinant
                       for i in range(3)) for k in range(3))


def clutch_brake_plans(response, capacity, brake_capacity, efficiency):
    """缓存当前轮胎子步的三个机械约束；迭代只改变自由速度和活动模式。"""
    plans, inverse_by_rows = [], {}
    clutch_modes = ("locked", "positive-slip", "negative-slip") if capacity else ("positive-slip", "negative-slip")
    brake_modes = ("locked", "positive-slip", "negative-slip") if brake_capacity else ("positive-slip", "negative-slip")
    for clutch_mode in clutch_modes:
        for gear_mode in ("positive-motion", "negative-motion", "static"):
            for sign in ((-1, 1) if gear_mode != "static" else (0,)):
                slope = (1 - efficiency if (gear_mode == "positive-motion") == (sign > 0)
                         else 1 - 1 / efficiency)
                for brake_mode in brake_modes:
                    rows = (response[0] if clutch_mode == "locked" else (1., 0., 0.),
                            response[1] if gear_mode == "static" else (-slope, 1., 0.),
                            response[2] if brake_mode == "locked" else (0., 0., 1.))
                    # 相同约束行只算一次；缓存仅属于当前子步，不近似响应系数。
                    if rows not in inverse_by_rows:
                        inverse_by_rows[rows] = _inverse_three(rows)
                    columns = inverse_by_rows[rows]
                    plans.append(((clutch_mode, gear_mode, brake_mode), sign, columns))
    return tuple(plans)


def clutch_brake_state(free, response, dt, capacity, brake_capacity, efficiency, plans, warm=None):
    """共同末状态同时决定传动和制动；暖模式仅改变检查顺序，不改变约束。"""
    tolerance = PORT_TOLERANCE
    order = ([warm] if warm is not None else []) + [i for i in range(len(plans)) if i != warm]
    for index in order:
        modes, sign, columns = plans[index]
        clutch_mode, gear_mode, brake_mode = modes
        rhs = (free[0] / dt if clutch_mode == "locked" else (capacity if clutch_mode == "positive-slip" else -capacity),
               free[1] / dt if gear_mode == "static" else 0.,
               free[2] / dt if brake_mode == "locked" else (brake_capacity if brake_mode == "positive-slip" else -brake_capacity))
        value = tuple(sum(columns[j][i] * rhs[j] for j in range(3)) for i in range(3))
        clutch, loss, brake = value
        if sign and clutch * sign < -tolerance:
            continue
        low, high = gear_loss_limits(clutch, efficiency)
        speeds = tuple(free[i] - dt * dot(response[i], value) for i in range(3))
        slip, speed, wheel_speed = speeds
        if abs(clutch) > capacity + tolerance or not low - tolerance <= loss <= high + tolerance:
            continue
        if abs(brake) > brake_capacity + tolerance:
            continue
        if clutch_mode == "locked" and abs(slip) > tolerance:
            continue
        if clutch_mode == "positive-slip" and slip < -tolerance or clutch_mode == "negative-slip" and slip > tolerance:
            continue
        if gear_mode == "static" and abs(speed) > tolerance:
            continue
        if gear_mode == "positive-motion" and (speed < -tolerance or abs(loss - high) > tolerance):
            continue
        if gear_mode == "negative-motion" and (speed > tolerance or abs(loss - low) > tolerance):
            continue
        if brake_mode == "locked" and abs(wheel_speed) > tolerance:
            continue
        if brake_mode == "positive-slip" and wheel_speed < -tolerance or brake_mode == "negative-slip" and wheel_speed > tolerance:
            continue
        return value, speeds, index
    raise ArithmeticError("离合/齿轮/制动共同末状态无可行解")
