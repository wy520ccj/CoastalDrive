"""只读保存的manifold/ESC轨迹，重建悬架冲量与剩余量。"""

import csv
import gzip
import json
from pathlib import Path


def cross(a, b):
    return (a[1]*b[2]-a[2]*b[1], a[2]*b[0]-a[0]*b[2], a[0]*b[1]-a[1]*b[0])


def add(a, b):
    return [x+y for x, y in zip(a, b)]


def sub(a, b):
    return [x-y for x, y in zip(a, b)]


directory = Path(__file__).parent
results = {}
for child in directory.glob("steps*-solver*"):
    with gzip.open(child / "manifold.jsonl.gz", "rt", encoding="utf-8") as stream:
        observations = [json.loads(line) for line in stream]
    with gzip.open(child / "esc.csv.gz", "rt", encoding="utf-8", newline="") as stream:
        rows = list(csv.DictReader(stream))
    summary = json.loads((child / "summary.json").read_text(encoding="utf-8"))
    config = summary["trial"]["config"]
    records = []
    for tick in (79, 80, 81, 82, 83):
        observed, row = observations[tick-1], rows[tick]
        summed_j, summed_l = [0., 0., 0.], [0., 0., 0.]
        wheels = []
        for index in range(4):
            prefix = f"state.wheel_contacts.{index}."
            load = float(row[prefix+"normal_load"])
            active = row[prefix+"in_contact"] == "True"
            if active:
                normal = [float(row[prefix+f"contact_normal.{axis}"]) for axis in range(3)]
                point = [float(row[prefix+f"contact_point.{axis}"]) for axis in range(3)]
                impulse = [component*load/120 for component in normal]
                angular = list(cross(sub(point, observed["post_bullet"]["position"]), impulse))
                summed_j, summed_l = add(summed_j, impulse), add(summed_l, angular)
            else:
                normal = point = None
                impulse = angular = [0., 0., 0.]
            wheels.append({"wheel": index, "Fn_n": load, "point": point, "normal": normal,
                           "J_ns": impulse, "L_about_post_cg_nms": angular})
        force_j = [component/120 for component in observed["pre_bullet"]["external_total_force_n"]]
        gravity_j = [0., 0., -config["mass"]*9.81/120]
        torque_j = [component/120 for component in observed["pre_bullet"]["external_total_torque_nm"]]
        reconstruction = add(add(add(observed["manifold_sum_impulse_ns"], summed_j), force_j), gravity_j)
        angular_reconstruction = add(add(observed["manifold_sum_angular_impulse_about_pre_cg_nms"], summed_l), torque_j)
        records.append({"tick": tick, "suspension_wheels": wheels, "suspension_J_sum_ns": summed_j,
                        "suspension_L_sum_about_post_cg_nms": summed_l, "gravity_J_ns": gravity_j,
                        "external_force_J_ns": force_j, "external_torque_J_nms": torque_j,
                        "delta_p_minus_all_reconstructed_ns": sub(observed["observed_delta_p_ns"], reconstruction),
                        "delta_L_minus_collision_suspension_external_nms": sub(observed["observed_delta_L_nms"], angular_reconstruction)})
    results[child.name] = records
report = {"protocol": "Fn*dt from completed raycast contacts; suspension moment about post-CG, collision about pre-CG. Pre external drag/rolling forces and gravity separate. Bullet2.84 ordering interpretation needs source confirmation; single precision/pose integration/inertia/force-prediction remainder not wholly collision.",
          "trials": results}
(directory / "suspension-reconstruction.json").write_text(json.dumps(report, indent=2)+"\n", encoding="utf-8")
