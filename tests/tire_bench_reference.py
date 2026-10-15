"""独立数学公式合成台架数据，仅用于拟合算法检查，不是实车证据。"""

import csv
import json
import math

from tire_calibration import FIELDS

TRUTH = {"road_friction": .92, "longitudinal_stiffness": 82000., "lateral_stiffness": 65000.,
         "tire_peak_load_exponent": .86, "longitudinal_load_exponent": .75, "lateral_load_exponent": .78}


def independent_force(kappa, alpha, load, nominal=2943.):
    ratio = load/nominal
    budget = .92*load*ratio**(-.14)
    vector = (82000*ratio**.75*kappa, -65000*ratio**.78*math.tan(alpha))
    norm = math.hypot(*vector)
    if norm == 0:
        return 0., 0.
    normalized = norm/(1.9*budget)
    magnitude = budget*math.sin(1.9*math.atan(normalized-.97*(normalized-math.atan(normalized))))
    return tuple(magnitude*component/norm for component in vector)


def write_bench(folder, *, invalid_combined=False, noise_N=0.):
    folder.mkdir(parents=True, exist_ok=True)
    path = folder/"bench.csv"
    rows = []
    for split, loads in (("train", (2000., 3500., 5000.)), ("validation", (2750., 4500.))):
        for load in loads:
            for kind in ("longitudinal", "lateral"):
                for index, slip in enumerate((-.3, -.15, -.08, -.025, -.002, 0., .002, .025, .08, .15, .3)):
                    kappa, alpha = (slip, 0.) if kind == "longitudinal" else (0., slip)
                    fx, fy = independent_force(kappa, alpha, load)
                    rows.append({"series": f"{split}-{kind}-{load}", "split": split, "kind": kind,
                                 "fz_N": load, "kappa": kappa, "alpha_rad": alpha,
                                 "fx_N": fx+noise_N*math.sin(index*2.3), "fy_N": fy+noise_N*math.cos(index*1.9)})
            if split == "validation":
                for kappa in (-.15, -.03, .03, .15):
                    for alpha in (-.12, -.04, .04, .12):
                        fx, fy = independent_force(kappa, alpha, load)
                        rows.append({"series": f"validation-combined-{load}", "split": split, "kind": "combined",
                                     "fz_N": load, "kappa": kappa, "alpha_rad": alpha,
                                     "fx_N": fx*(.5 if invalid_combined else 1), "fy_N": fy})
    with path.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows(rows)
    conditions = {"tire_id": "algorithm-check-tire", "surface_id": "synthetic-reference-surface",
                  "pressure_kpa": 230., "temperature_c": 25., "speed_mps": 20., "camber_rad": 0.,
                  "source": "tests/tire_bench_reference.py independent equations; not measured",
                  "source_kind": "synthetic", "measurement_mode": "steady_state", "installation": "same_tire_all_wheels"}
    conditions["slip_convention"] = "drive_positive_alpha_right"
    condition_path = folder/"conditions.json"
    condition_path.write_text(json.dumps(conditions, indent=2), encoding="utf-8")
    return path, condition_path
