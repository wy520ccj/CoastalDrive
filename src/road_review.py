"""只读道路完成步；按首次向前到达的位置对齐，不补失败后的数据。"""

from dataclasses import asdict

from slalom_lesson import GATES


def sample_at(record, distance):
    if distance < 0:
        return None
    states, rows = record.snapshots, record.rows
    initial = states[0]
    if distance == 0:
        car = initial.player
        return {"position": 0., "time": 0., "x": car.position[0], "speed_kph": car.speed*3.6,
            "heading_deg": car.heading, "steering_deg": car.steering, "beta_deg": car.dynamics.sideslip,
            "roll_deg": car.roll, "control": None, "completed_tick": 0, "fraction": 0.}
    previous, py, pt = initial.player, 0., 0.
    for index, (state, row) in enumerate(zip(states[1:], rows, strict=True)):
        current, y, time = state.player, row["position"], row["time"]
        if py <= distance <= y and y > py:
            fraction = (distance-py)/(y-py)
            def blend(a, b, weight=fraction):
                return a+(b-a)*weight
            return {"position": distance, "time": blend(pt, time),
                "x": blend(previous.position[0], current.position[0]),
                "speed_kph": blend(previous.speed, current.speed)*3.6,
                "heading_deg": previous.heading+((current.heading-previous.heading+180)%360-180)*fraction,
                "steering_deg": blend(previous.steering, current.steering),
                "beta_deg": blend(previous.dynamics.sideslip, current.dynamics.sideslip),
                "roll_deg": blend(previous.roll, current.roll),
                "control": asdict(record.controls[index]), "completed_tick": row["tick"],
                "fraction": fraction}
        previous, py, pt = current, y, time
    return None


def gate_crossings(record):
    result = record.metadata["result"]
    gates = []
    for index, clearance in enumerate(result["clearances"]):
        distance, target = GATES[index]
        sample = sample_at(record, distance)
        if sample is None:
            raise ValueError("原判门结果缺少对应的完成步")
        gates.append({**sample, "gate": index+1, "target_x": target,
            "center_error_m": result["errors"][index], "clearance_m": clearance,
            "passed": index < result["gates"]})
    return gates


def focus_position(records):
    gates = [gate for record in records for gate in gate_crossings(record)]
    failed = next((gate for gate in gates if not gate["passed"]), None)
    if failed is not None:
        return failed["position"]
    if gates:
        return min(gates, key=lambda gate: gate["clearance_m"])["position"]
    return max((row["position"] for record in records for row in record.rows), default=0.)
