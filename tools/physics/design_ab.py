"""工程车辆参数与三驱动布局的定向实验，复用实际Bullet平面标准输入。"""

import argparse
import hashlib
import json
import sys
from dataclasses import replace
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT/"src"), str(ROOT/"tools")]
from physics.esc_probe import write_csv
from physics.reference_ab import run_trial

from vehicle_designs import REFERENCE_DESIGN
from vehicle_parameters import load_vehicle_config, save_vehicle_config


def run(output, designs):
    output.mkdir(parents=True, exist_ok=False)
    configs = {layout: load_vehicle_config(designs/f"reference-{layout}.json", REFERENCE_DESIGN)
               for layout in ("rwd", "fwd", "awd")}
    base = configs["rwd"]
    cases = [
        ("acceleration-base", "B1-wheel-inertia", base, 480),
        ("acceleration-mass1500", "B1-wheel-inertia", replace(base, mass=1500.), 480),
        ("brake-base", "B2-cg-height", base, 240),
        ("brake-cg062", "B2-cg-height", replace(base, center_of_mass_height=.62), 240),
        ("brake-spring72000", "B2-cg-height", replace(base, suspension_spring_rates=(72000.,)*4), 240),
        ("stop-base", "B3-asphalt-mu", base, 720),
        ("stop-mu065", "B3-asphalt-mu", replace(base, road_friction=.65), 720),
        *[("lowmu-"+layout, "B1-wheel-inertia", replace(config, road_friction=.25), 480)
          for layout, config in configs.items()],
    ]
    hashes = lambda: {p.relative_to(ROOT).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
                      for folder in ("src", "tools/physics") for p in sorted((ROOT/folder).rglob("*.py"))}
    report = {"status": "running", "source_before": hashes(), "results": [],
              "protocol": {"physics_hz": 120, "trace_hz": 120, "settle_ticks": 240,
                           "world": "same gravity -9.81 and horizontal BulletPlaneShape",
                           "input": "same direct VehicleCommand within each comparison",
                           "scope": "mass/CG/spring/friction/layout directional experiments; not full calibration or stage gate"}}

    def save():
        (output/"summary.json").write_text(json.dumps(report, ensure_ascii=False, indent=2, allow_nan=False), encoding="utf-8")

    save()
    try:
        for index, (label, case, config, ticks) in enumerate(cases):
            save_vehicle_config(output/(label+".json"), config,
                                metadata={"basis": "exported complete engineering design", "experiment": label})
            summary, rows = run_trial(case, config, ticks, sample_stride=1)
            residual = max(abs(row[f"state.wheel_dynamics.{i}.force_residual"]) for row in rows for i in range(4))
            assert residual < .001
            trace = label+".csv.gz"
            write_csv(output/trace, rows)
            report["results"].append({"label": label, **summary, "trace": trace,
                                      "trace_sha256": hashlib.sha256((output/trace).read_bytes()).hexdigest(),
                                      "max_tire_residual_n": residual})
            save()
            print(f"DONE {label} v={summary['final_speed_mps']:.6f} distance={summary['longitudinal_displacement_m']:.6f}", flush=True)
    except (ArithmeticError, AssertionError, ValueError, OSError) as error:
        report.update(status="failed", error=repr(error), failed_case=cases[index][0],
                      not_run=[row[0] for row in cases[index+1:]])
        raise
    else:
        report["status"] = "completed"
    finally:
        report["source_after"] = hashes()
        report["source_stable"] = report["source_before"] == report["source_after"]
        save()
    assert report["source_stable"]


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--designs", type=Path, default=ROOT/"docs/evidence/PHYS-DESIGN-01/designs")
    args = parser.parse_args()
    run(args.output, args.designs)
