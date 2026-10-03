"""下一功能的独立机械台架：固定轴方向、三维壳体反力、发动机惯量及有限离合。"""

import csv
import hashlib
import json
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[3]
OUT = Path(__file__).with_name("mechanical-clutch-bench")


def hashes():
    return {p.relative_to(ROOT).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
            for folder in ("src", "tests", "tools") for p in sorted((ROOT/folder).rglob("*.py"))}


def unit(values):
    vector = np.array(values, dtype=float)
    return vector/np.linalg.norm(vector)


def geometry(layout, ratio):
    body_inertia = np.array(((1919.56, 30, -10), (30, 511.56, 5), (-10, 5, 2290)))
    engine_axis, left_axis, right_axis = (
        (unit((0, 1, 0)), unit((-1, 0, 0)), unit((-1, 0, 0))) if layout == "orthogonal"
        else (unit((.3, .9, .1)), unit((-.98, .2, 0)), unit((-.98, -.2, 0))))
    mass = np.zeros((6, 6))
    mass[:3, :3] = body_inertia
    mass[3:, 3:] = np.diag((.2, 1.8, 1.8))
    reaction_axis = engine_axis-ratio*(left_axis+right_axis)/2
    constraint = np.r_[-reaction_axis, 1, -ratio/2, -ratio/2]
    return mass, constraint, (engine_axis, left_axis, right_axis)


def angular_momentum(q, mass, axes):
    return mass[:3, :3]@q[:3]+sum(mass[i+3, i+3]*q[i+3]*axes[i] for i in range(3))


def run(layout, ratio, substeps, case):
    name, capacity, engine_torque, wheel_loads, engine_speed, wheel_speeds = case
    mass, c, axes = geometry(layout, ratio)
    inverse = np.linalg.inv(mass)
    response = inverse@c
    mobility = float(c@response)
    dt = 1/120/substeps
    sign = np.sign(ratio)
    output_torques = np.array(wheel_loads)*sign
    force = np.r_[-engine_torque*axes[0], engine_torque, output_torques]
    q = np.r_[.1, -.2, .3, engine_speed, np.array(wheel_speeds)*sign]
    kkt = np.block([[mass, (dt*c)[:, None]], [c[None, :], np.zeros((1, 1))]])
    rows = []
    maxima = dict(energy_balance_j=0., momentum_balance_nms=0.,
                  complementarity_nm=0., unconstrained_kkt_torque_nm=0., equation_residual_nms=0.)
    clutch_total = numerical_total = engine_total = output_total = 0.
    for tick in range(int(.4/dt)):
        old = q.copy()
        free = old+dt*(inverse@force)
        requested = float(c@free)/(dt*mobility)
        torque = min(capacity, max(-capacity, requested))
        q = free-dt*torque*response
        slip = float(c@q)
        clutch_work = dt*torque*slip
        delta = q-old
        numerical_loss = .5*float(delta@mass@delta)
        engine_work = dt*engine_torque*(q[3]-float(axes[0]@q[:3]))
        output_work = dt*float(output_torques@q[4:])
        energy_error = .5*float(q@mass@q-old@mass@old)+clutch_work+numerical_loss-engine_work-output_work
        angular_error = angular_momentum(q, mass, axes)-angular_momentum(old, mass, axes)
        angular_error -= dt*(output_torques[0]*axes[1]+output_torques[1]*axes[2])
        projected = min(capacity, max(-capacity, torque+slip/(dt*mobility)))
        independent = np.linalg.solve(kkt, np.r_[mass@free, 0])[-1]
        equation_error = mass@delta-dt*(force-torque*c)
        values = (abs(energy_error), float(np.linalg.norm(angular_error)), abs(torque-projected),
                  abs(requested-independent), float(np.linalg.norm(equation_error)))
        for key, value in zip(maxima, values):
            maxima[key] = max(maxima[key], value)
        assert values[0] < 1e-7, (name, "energy", values)
        assert values[1] < 1e-9, (name, "momentum", values)
        assert values[2] < 1e-7 and values[3] < 1e-7, (name, "capacity/KKT", values)
        assert values[4] < 1e-9, (name, "equation", values)
        assert clutch_work > -1e-9, (name, "negative clutch work", clutch_work)
        assert abs(torque) <= capacity
        clutch_total += clutch_work
        numerical_total += numerical_loss
        engine_total += engine_work
        output_total += output_work
        row = [tick+1, (tick+1)*dt, *q.tolist(), torque, slip, clutch_work, numerical_loss,
               engine_work, output_work, energy_error, float(np.linalg.norm(angular_error))]
        assert all(np.isfinite(value) for value in row)
        rows.append(row)
    path = OUT/f"{layout}-{ratio:g}-{substeps}-{name}.csv"
    with path.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.writer(stream)
        writer.writerow(("tick", "time_s", "body_wx", "body_wy", "body_wz", "engine_absolute_omega",
                         "left_absolute_omega", "right_absolute_omega", "clutch_torque_nm", "clutch_slip_radps",
                         "clutch_work_j", "BE_loss_j", "combustion_work_j", "external_output_work_j",
                         "energy_balance_j", "momentum_balance_nms"))
        writer.writerows(rows)
    return {"layout": layout, "ratio": ratio, "substeps": substeps, "case": name,
            "design_parameters": {"mass_matrix": mass.tolist(), "fixed_axes": [a.tolist() for a in axes],
                                  "clutch_capacity_nm": capacity, "engine_torque_nm": engine_torque,
                                  "external_output_torques_nm": output_torques.tolist()},
            "row_count": len(rows), "final_state": q.tolist(), "maxima": maxima,
            "clutch_work_j": clutch_total, "BE_loss_j": numerical_total,
            "combustion_work_j": engine_total, "external_output_work_j": output_total,
            "csv": path.name, "csv_sha256": hashlib.sha256(path.read_bytes()).hexdigest()}


def omitted_reaction_control():
    mass, c, axes = geometry("orthogonal", 12)
    old = np.r_[.1, -.2, .3, 500, 10, 10]
    dt, torque = 1/240, 40
    broken = c.copy()
    broken[:3] = 0
    new = old-dt*torque*np.linalg.solve(mass, broken)
    error = float(np.linalg.norm(angular_momentum(new, mass, axes)-angular_momentum(old, mass, axes)))
    assert error > 1
    return {"deliberately_omitted": "clutch reaction on chassis", "momentum_error_nms": error,
            "detected_by_original_momentum_gate": error > 1e-9}


if __name__ == "__main__":
    before = hashes()
    OUT.mkdir(exist_ok=True)
    cases = (("free", 0, 120, (0, 0), 100, (3, 7)),
             ("positive_slip", 40, 0, (0, 0), 500, (10, 10)),
             ("negative_slip", 40, 0, (0, 0), 100, (50, 50)),
             ("lock", 100000, 0, (0, 0), 500, (10, 20)),
             ("fueled_load", 250, 150, (-30, -20), 200, (10, 10)),
             ("unequal_wheels", 500, 80, (0, 0), 240, (10, 30)))
    trials = [run(layout, ratio, substeps, case) for layout in ("orthogonal", "skew")
              for ratio in (12, -12) for substeps in (2, 4, 8, 16) for case in cases]
    after = hashes()
    convergence = []
    for layout in ("orthogonal", "skew"):
        for ratio in (12, -12):
            selected = [r for r in trials if r["layout"] == layout and r["ratio"] == ratio
                        and r["case"] == "positive_slip"]
            losses = [r["BE_loss_j"] for r in selected]
            assert all(b < a for a, b in zip(losses, losses[1:]))
            convergence.append({"layout": layout, "ratio": ratio, "BE_losses_j_2_4_8_16": losses})
    report = {"claim": "independent fixed-axis mechanical prototype; not production driving or gear-shift acceptance",
              "source_stable": before == after, "source_sha256_before": before, "source_sha256_after": after,
              "fixture": {"duration_s": .4, "axis_transport_or_gyroscopic_terms": False,
                          "tires_brakes_shift_controller": False, "gear_efficiency": 1,
                          "parameters": "synthetic design values, not real-car measurements"},
              "negative_control": omitted_reaction_control(), "convergence": convergence,
              "trials": trials}
    (OUT/"summary.json").write_text(json.dumps(report, indent=2, allow_nan=False)+"\n", encoding="utf-8")
    print(json.dumps({"trials": len(trials), "rows": sum(r["row_count"] for r in trials),
                      "source_stable": report["source_stable"], "negative_control": report["negative_control"],
                      "maxima": {k: max(r["maxima"][k] for r in trials) for k in trials[0]["maxima"]}}))
