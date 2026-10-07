"""实体输入轴的离合、齿轮反力/效率、同步器与单轮制动端口。"""

import math
from itertools import product

from transmission_ports import PORT_TOLERANCE, _inverse_three, gear_loss_limits


def dot(first, second):
    return sum(a * b for a, b in zip(first, second))


def shaft_gradients(engine_axis, shaft_axis, wheel_axes, weights, ratio):
    """九维绝对速度中，离合与齿轮分别作用于两根实体轴和真实轮轴。"""
    wheel_ratios = tuple(ratio * weight for weight in weights)
    drive_axis = tuple(sum(wheel_ratios[i] * wheel_axes[i][a] for i in range(4)) for a in range(3))
    clutch = tuple(shaft_axis[a] - engine_axis[a] for a in range(3)) + (1., -1.) + (0.,) * 4
    gear = tuple(-shaft_axis[a] - drive_axis[a] for a in range(3)) + (0., 1.) + tuple(-r for r in wheel_ratios)
    loss = drive_axis + (0., 0.) + wheel_ratios
    return clutch, gear, loss


def shaft_brake_plans(response, capacity, brake_capacity, efficiency):
    """已挂挡先消去理想齿比约束；损失区间取实际齿轮反力，而非离合矩。"""
    ports = (0, 2, 3)
    gear_response = tuple(response[1][j] / response[1][1] for j in ports)
    reduced = tuple(tuple(response[i][j] - response[i][1] * response[1][j] / response[1][1]
                          for j in ports) for i in ports)
    plans, inverses = [], {}
    clutch_modes = (0, 1, -1) if capacity else (1, -1)
    brake_modes = (0, 1, -1) if brake_capacity else (1, -1)
    for clutch_mode, motion, brake_mode in product(clutch_modes, (1, -1, 0), brake_modes):
        for sign in ((1, -1) if motion else (0,)):
            slope = (1 - efficiency if motion * sign > 0 else 1 - 1 / efficiency)
            rows = (reduced[0] if clutch_mode == 0 else (1., 0., 0.),
                    reduced[1] if motion == 0 else tuple(slope * gear_response[j] + float(j == 1) for j in range(3)),
                    reduced[2] if brake_mode == 0 else (0., 0., 1.))
            if rows not in inverses:
                inverses[rows] = _inverse_three(rows)
            plans.append(((clutch_mode, motion, brake_mode), sign, slope, inverses[rows]))
    return tuple(plans)


def shaft_brake_state(free, response, dt, capacity, brake_capacity, efficiency, plans, warm=None):
    """四端口顺序为离合滑差、齿比误差、齿轮输入速、单轮相对速。"""
    tolerance = PORT_TOLERANCE
    ports = (0, 2, 3)
    gear_free = free[1] / (dt * response[1][1])
    reduced_free = tuple(free[i] - response[i][1] * free[1] / response[1][1] for i in ports)
    order = ([warm] if warm is not None else []) + [i for i in range(len(plans)) if i != warm]
    for index in order:
        modes, sign, slope, columns = plans[index]
        clutch_mode, motion, brake_mode = modes
        rhs = (reduced_free[0] / dt if clutch_mode == 0 else clutch_mode * capacity,
               reduced_free[1] / dt if motion == 0 else slope * gear_free,
               reduced_free[2] / dt if brake_mode == 0 else brake_mode * brake_capacity)
        clutch, loss, brake = tuple(sum(columns[j][i] * rhs[j] for j in range(3)) for i in range(3))
        if abs(clutch) > capacity + tolerance or abs(brake) > brake_capacity + tolerance:
            continue
        gear = gear_free - sum(response[1][j] * value / response[1][1]
                               for j, value in zip(ports, (clutch, loss, brake)))
        low, high = gear_loss_limits(gear, efficiency)
        if not low - tolerance <= loss <= high + tolerance or sign and gear * sign < -tolerance:
            continue
        values = clutch, gear, loss, brake
        speeds = tuple(free[i] - dt * dot(response[i], values) for i in range(4))
        slip, error, speed, wheel_speed = speeds
        if abs(error) > tolerance:
            continue
        if clutch_mode == 0 and abs(slip) > tolerance or clutch_mode * slip < -tolerance:
            continue
        if brake_mode == 0 and abs(wheel_speed) > tolerance or brake_mode * wheel_speed < -tolerance:
            continue
        if motion == 0 and abs(speed) > tolerance:
            continue
        if motion > 0 and (speed < -tolerance or abs(loss - high) > tolerance):
            continue
        if motion < 0 and (speed > tolerance or abs(loss - low) > tolerance):
            continue
        return values, speeds, index
    raise ArithmeticError("实体输入轴/离合/齿轮/制动共同末状态无可行解")


def shaft_brake_response(direction, response, plan):
    """同一活动分区的精确转矩导数，供轮胎接触牛顿导数使用。"""
    modes, _sign, slope, columns = plan
    ports = (0, 2, 3)
    gear_free = direction[1] / response[1][1]
    reduced = tuple(direction[i] - response[i][1] * gear_free for i in ports)
    rhs = (reduced[0] if modes[0] == 0 else 0.,
           reduced[1] if modes[1] == 0 else slope * gear_free,
           reduced[2] if modes[2] == 0 else 0.)
    clutch, loss, brake = tuple(sum(columns[j][i] * rhs[j] for j in range(3)) for i in range(3))
    gear = gear_free - sum(response[1][j] * value / response[1][1]
                           for j, value in zip(ports, (clutch, loss, brake)))
    return clutch, gear, loss, brake


def synchronizer_brake_plans(response, capacities):
    """未挂挡的离合/有限同步锥/单轮制动；零容量端口只能传零矩。"""
    plans, inverses = [], {}
    choices = [(0, 1, -1) if capacity else (1, -1) for capacity in capacities]
    for modes in product(*choices):
        rows = tuple(response[i] if mode == 0 else tuple(float(i == j) for j in range(3))
                     for i, mode in enumerate(modes))
        if rows not in inverses:
            inverses[rows] = _inverse_three(rows)
        plans.append((modes, inverses[rows]))
    return tuple(plans)


def synchronizer_brake_state(free, response, dt, capacities, plans, warm=None):
    """锁合或容量饱和均由末滑差决定，不设置转速、不按固定时间宣布同步。"""
    order = ([warm] if warm is not None else []) + [i for i in range(len(plans)) if i != warm]
    for index in order:
        modes, columns = plans[index]
        rhs = tuple(free[i] / dt if mode == 0 else mode * capacities[i] for i, mode in enumerate(modes))
        values = tuple(sum(columns[j][i] * rhs[j] for j in range(3)) for i in range(3))
        speeds = tuple(free[i] - dt * dot(response[i], values) for i in range(3))
        if any(abs(value) > capacity + PORT_TOLERANCE for value, capacity in zip(values, capacities)):
            continue
        if any(abs(speed) > PORT_TOLERANCE if mode == 0 else mode * speed < -PORT_TOLERANCE
               for mode, speed in zip(modes, speeds)):
            continue
        return values, speeds, index
    raise ArithmeticError("实体输入轴/离合/同步器/制动共同末状态无可行解")


def synchronizer_brake_response(direction, plan):
    """有限同步活动分区的转矩导数。"""
    modes, columns = plan
    rhs = tuple(direction[i] if mode == 0 else 0. for i, mode in enumerate(modes))
    return tuple(sum(columns[j][i] * rhs[j] for j in range(3)) for i in range(3))


def brake_increment(response, speeds, torques, capacities, dt, diagonal):
    """联合修正四轮制动；饱和行指定容量，锁合行指定末相对速为零。"""
    rows = []
    for i in range(4):
        demand = torques[i] + speeds[i] / (dt * diagonal[i])
        if abs(demand) < capacities[i]:
            rows.append(list(response[i]) + [speeds[i] / dt])
        else:
            target = max(-capacities[i], min(capacities[i], demand))
            rows.append([float(i == j) for j in range(4)] + [target - torques[i]])
    pivots, row = [], 0
    rounding = 16 * math.ulp(max(abs(value) for line in rows for value in line[:4]))
    for column in range(4):
        pivot = max(range(row, 4), key=lambda i: abs(rows[i][column]))
        if abs(rows[pivot][column]) <= rounding:
            # 全轮锁合与齿轮静止可能具有相关约束；保留旧转矩的零空间分量。
            continue
        rows[row], rows[pivot] = rows[pivot], rows[row]
        scale = rows[row][column]
        rows[row] = [value / scale for value in rows[row]]
        for i in range(4):
            if i != row:
                factor = rows[i][column]
                rows[i] = [rows[i][j] - factor * rows[row][j] for j in range(5)]
        pivots.append((row, column))
        row += 1
        if row == 4:
            break
    result = [0.] * 4
    for row, column in pivots:
        result[column] = rows[row][4]
    return tuple(result)
