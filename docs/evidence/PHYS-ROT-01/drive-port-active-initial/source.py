"""传动预研：同一隐式机械阻抗的离合/齿轮二维活动集，生产源码只读。"""

import hashlib
import json
import math
import random
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
OUT = Path(__file__).with_name("drive-port-active-initial")
EPS = 1e-11


def dot(a, b):
    return sum(x * y for x, y in zip(a, b))


def limits(clutch, eta):
    if clutch >= 0:
        return -(1 / eta - 1) * clutch, (1 - eta) * clutch
    return (1 - eta) * clutch, -(1 / eta - 1) * clutch


def active(delta_free, input_free, dcc, dcl, dll, h, capacity, eta):
    """枚举有限离合与齿轮运动/静止的实际约束，不用迭代失败回退。"""
    candidates = []

    def accept(clutch, loss, clutch_mode, gear_mode):
        slip = delta_free - h * (dcc * clutch + dcl * loss)
        speed = input_free - h * (dcl * clutch + dll * loss)
        low, high = limits(clutch, eta)
        if abs(clutch) > capacity + EPS or loss < low - EPS or loss > high + EPS:
            return
        if clutch_mode == "locked" and abs(slip) > EPS:
            return
        if clutch_mode == "positive-slip" and slip < -EPS:
            return
        if clutch_mode == "negative-slip" and slip > EPS:
            return
        if gear_mode == "static" and abs(speed) > EPS:
            return
        if gear_mode == "positive-motion" and (speed < -EPS or abs(loss - high) > EPS):
            return
        if gear_mode == "negative-motion" and (speed > EPS or abs(loss - low) > EPS):
            return
        candidates.append((clutch, loss, slip, speed, clutch_mode, gear_mode))

    for direction in (-1, 1):
        gear_mode = "positive-motion" if direction > 0 else "negative-motion"
        for clutch_sign in (-1, 1):
            slope = 1 - eta if direction * clutch_sign > 0 else 1 - 1 / eta
            clutch = delta_free / (h * (dcc + dcl * slope))
            if clutch * clutch_sign >= -EPS:
                accept(clutch, slope * clutch, "locked", gear_mode)
            clutch = clutch_sign * capacity
            accept(clutch, slope * clutch,
                   "positive-slip" if clutch_sign > 0 else "negative-slip", gear_mode)
    determinant = dcc * dll - dcl * dcl
    clutch = (dll * delta_free - dcl * input_free) / (h * determinant)
    loss = (dcc * input_free - dcl * delta_free) / (h * determinant)
    accept(clutch, loss, "locked", "static")
    for clutch_sign in (-1, 1):
        clutch = clutch_sign * capacity
        loss = (input_free / h - dcl * clutch) / dll
        accept(clutch, loss, "positive-slip" if clutch_sign > 0 else "negative-slip", "static")
    if not candidates:
        raise ArithmeticError("传动活动集无可行共同末状态")
    first = candidates[0]
    # 边界可以有多个模式标签，但不能有不同机械解。
    assert all(max(abs(c[i] - first[i]) for i in range(4)) < 1e-8 for c in candidates)
    return first, len(candidates)


def bisect(function, low, high):
    a, b = function(low), function(high)
    assert a >= -EPS and b <= EPS, (a, b)
    for _ in range(100):
        middle = (low + high) / 2
        value = function(middle)
        if abs(value) < 1e-13:
            return middle
        if value > 0:
            low = middle
        else:
            high = middle
    return (low + high) / 2


def nested(delta_free, input_free, dcc, dcl, dll, h, capacity, eta):
    def gear(clutch):
        low, high = limits(clutch, eta)
        def speed(loss):
            return input_free - h * (dcl * clutch + dll * loss)
        if speed(low) < -EPS:
            loss = low
        elif speed(high) > EPS:
            loss = high
        else:
            loss = bisect(speed, low, high)
        return delta_free - h * (dcc * clutch + dcl * loss), loss
    if gear(-capacity)[0] < -EPS:
        clutch = -capacity
    elif gear(capacity)[0] > EPS:
        clutch = capacity
    else:
        clutch = bisect(lambda c: gear(c)[0], -capacity, capacity)
    return clutch, gear(clutch)[1]


def source_hashes():
    return {p.relative_to(ROOT).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
            for folder in ("src", "tests", "tools") for p in sorted((ROOT / folder).rglob("*.py"))}


def main():
    OUT.mkdir(exist_ok=False)
    (OUT / "source.py").write_bytes(Path(__file__).read_bytes())
    before = source_hashes()
    rng = random.Random(20261003)
    cases = []
    for index in range(360):
        h = (1 / 240, 1 / 960)[index % 2]
        ratio = (12., -12., 4., -4.)[index % 4]
        eta = (.88, 1.)[(index // 4) % 2]
        drag = (0., .12, .6)[(index // 8) % 3]
        engine_inertia, wheel_inertia = .2, 1.15
        inertia = (1900., 510., 2200.)
        ae = (0., 1., 0.)
        bank, steer = rng.uniform(-.4, .4), rng.uniform(-.5, .5)
        e = (math.cos(steer) * math.cos(bank), -math.sin(steer), math.cos(steer) * math.sin(bank))
        # q=(车身角速3, 曲轴绝对正转, 两后轮正滚动绝对转速)。
        gc = tuple(-ae[a] - ratio * e[a] for a in range(3)) + (1., -ratio / 2, -ratio / 2)
        gl = tuple(ratio * e[a] for a in range(3)) + (0., ratio / 2, ratio / 2)
        ge = tuple(-v for v in ae) + (1., 0., 0.)
        inverse = tuple(1 / v for v in inertia) + (1 / engine_inertia, 1 / wheel_inertia, 1 / wheel_inertia)
        mg = tuple(inverse[i] * ge[i] for i in range(6))
        factor = h * drag / (1 + h * drag * dot(ge, mg))
        def mobility(vector):
            return tuple(inverse[i] * vector[i] - factor * mg[i] * dot(mg, vector) for i in range(6))
        q0 = tuple(rng.uniform(-.3, .3) for _ in range(3)) + (rng.uniform(-100, 500), rng.uniform(-80, 80), rng.uniform(-80, 80))
        gross = rng.uniform(0, 250)
        qfree = mobility(tuple(q0[i] / inverse[i] + h * gross * ge[i] for i in range(6)))
        dfree, xfree = dot(gc, qfree), dot(gl, qfree)
        mcc, mcl, mll = dot(gc, mobility(gc)), dot(gc, mobility(gl)), dot(gl, mobility(gl))
        capacity = (0., 50., 300.)[(index // 24) % 3]
        if index % 10 == 0:
            # 构造可行的静止区间点，再由阻抗反推自由端，直接覆盖静止约束。
            target_c = capacity * .7
            low, high = limits(target_c, eta)
            target_l = (low + high) / 2
            dfree, xfree = h * (mcc * target_c + mcl * target_l), h * (mcl * target_c + mll * target_l)
            det = mcc * mll - mcl * mcl
            shift_c = (mll * (dfree - dot(gc, qfree)) - mcl * (xfree - dot(gl, qfree))) / det
            shift_l = (mcc * (xfree - dot(gl, qfree)) - mcl * (dfree - dot(gc, qfree))) / det
            qfree = tuple(qfree[i] + shift_c * mobility(gc)[i] + shift_l * mobility(gl)[i] for i in range(6))
            # 对应同一无约束机械初态，不修改末速度。
            ue_free = dot(ge, qfree)
            q0 = tuple(qfree[i] + h * inverse[i] * (drag * ue_free - gross) * ge[i] for i in range(6))
        result, feasible = active(dfree, xfree, mcc, mcl, mll, h, capacity, eta)
        clutch, loss, slip, speed, cmode, gmode = result
        reference = nested(dfree, xfree, mcc, mcl, mll, h, capacity, eta)
        difference = max(abs(result[i] - reference[i]) for i in range(2))
        assert difference < 1e-8, (index, result, reference)
        qend = tuple(qfree[i] - h * (clutch * mobility(gc)[i] + loss * mobility(gl)[i]) for i in range(6))
        ue = dot(ge, qend)
        energy = .5 * sum((qend[i]**2 - q0[i]**2 + (qend[i] - q0[i])**2) / inverse[i] for i in range(6))
        heat = h * (drag * ue * ue + clutch * slip + loss * speed)
        error = energy + heat - h * gross * ue
        assert abs(error) < 3e-9, (index, error)
        assert h * clutch * slip >= -1e-9 and h * loss * speed >= -1e-9
        cases.append({"index":index,"h":h,"ratio":ratio,"eta":eta,"drag":drag,"capacity":capacity,
                      "q0":q0,"qend":qend,"gross":gross,"gc":gc,"gl":gl,
                      "delta_free":dfree,"input_free":xfree,"mobility":[mcc,mcl,mll],
                      "clutch":clutch,"loss":loss,"slip":slip,"speed":speed,
                      "clutch_mode":cmode,"gear_mode":gmode,"feasible_labels":feasible,
                      "nested":reference,"difference":difference,"energy_error":error})
    after = source_hashes()
    assert before == after
    report = {"claim":"fixed mechanical mobility port proof only; no contacts, gyro or native integration; not production validation",
              "source_before":before,"source_after":after,"source_stable":before==after,"cases":cases,
              "maximum_energy_error_j":max(abs(c["energy_error"]) for c in cases),
              "maximum_nested_torque_difference_nm":max(c["difference"] for c in cases),
              "mode_counts":{f"{a}/{b}":sum(c["clutch_mode"]==a and c["gear_mode"]==b for c in cases)
                             for a in ("locked","positive-slip","negative-slip")
                             for b in ("static","positive-motion","negative-motion")}}
    (OUT / "summary.json").write_text(json.dumps(report, indent=2, allow_nan=False), encoding="utf-8")
    print({k: report[k] for k in ("maximum_energy_error_j","maximum_nested_torque_difference_nm","mode_counts","source_stable")})


if __name__ == "__main__":
    main()
