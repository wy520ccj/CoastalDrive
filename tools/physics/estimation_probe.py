"""真实120Hz驾驶、GNSS失联与独立估计的短真值对照。"""

import argparse
import hashlib
import json
import math
import sys
from dataclasses import asdict
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT / "src"), str(ROOT / "tools")]
from physics.esc_probe import write_csv
from physics.reference_ab import _flatten

from driving_modes import REFERENCE_CAR
from estimation_rotation import conjugate, log, multiply
from sensor_run import SensingRun, truth_sample
from sensor_sampling import SensorConfig
from simulation import Simulation
from vehicle_designs import GR86_DESIGN
from vehicle_state import VehicleCommand


def run_case(case, config, seed, output, ticks=960):
    track, shape = ("endless", "hills") if case == "hills" else ("test", "straight")
    sim = Simulation(seed, track=track, road_shape=shape, traffic_count=0, config=config)
    try:
        for _ in range(240):
            sim.step(VehicleCommand())
        initial = sim.snapshot()
        sensors = SensorConfig(gnss_outages=((initial.tick + 360, initial.tick + 720),))
        sensing = SensingRun(initial, config, sensors, seed=seed + 100)
        rows, positions, velocities, rotations = [], [], [], []
        gnss, rejected = 0, 0
        for local_tick in range(1, ticks + 1):
            command = VehicleCommand(throttle=.6 if local_tick <= 360 else .2 if local_tick <= 720 else 0.,
                                     brake=.8 if local_tick > 720 else 0.,
                                     steering=2. if case == "turn-brake" and local_tick > 360 else 0., direction=1)
            sim.step(command)
            snapshot = sim.snapshot()
            result = sensing.observe(snapshot)
            true = truth_sample(snapshot)
            if result.reset:
                raise AssertionError("短估计实验出现实际恢复/reset，须作为独立工况记录")
            positions.append(np.asarray(result.estimate.position) - true.position)
            velocities.append(np.asarray(result.estimate.velocity) - true.velocity)
            rotations.append(log(multiply(conjugate(true.orientation), result.estimate.orientation)))
            gnss += len(result.measurements.gnss)
            rejected += result.measurements.wheels is not None and result.estimate.wheel_accepted is False
            row = {"tick": snapshot.tick, "time_s": snapshot.time}
            for prefix, value in (("command", command), ("truth", true), ("measurements", result.measurements),
                                  ("estimate", result.estimate)):
                _flatten(prefix, asdict(value), row)
            _flatten("truth.accel_bias", tuple(sensing.sensors.accel_bias), row)
            _flatten("truth.gyro_bias", tuple(sensing.sensors.gyro_bias), row)
            rows.append(row)
        path = output / (case + ".csv.gz")
        write_csv(path, rows)
        return {"case": case, "ticks": ticks, "gnss_deliveries": gnss, "wheel_innovation_rejections": int(rejected),
                "position_component_rmse_m": float(np.sqrt(np.mean(np.asarray(positions)**2))),
                "velocity_component_rmse_m_s": float(np.sqrt(np.mean(np.asarray(velocities)**2))),
                "rotation_vector_rmse_rad": float(np.sqrt(np.mean(np.asarray(rotations)**2))),
                "last_orientation_error_deg": math.degrees(float(np.linalg.norm(rotations[-1]))),
                "minimum_covariance_eigenvalue": float(np.linalg.eigvalsh(sensing.timeline.estimator.covariance).min()),
                "final_estimate": asdict(result.estimate), "initialization": "known reset/experiment pose and velocity only; zero unknown bias estimate",
                "sensor_config": asdict(sensors), "trace": path.name,
                "trace_sha256": hashlib.sha256(path.read_bytes()).hexdigest()}
    finally:
        sim.close()


def run(output, design, cases, seed):
    output.mkdir(parents=True, exist_ok=False)
    config = {"reference": REFERENCE_CAR, "gr86": GR86_DESIGN}[design]
    paths = tuple(path for tree in ("src", "tools/physics") for path in (ROOT / tree).rglob("*.py"))
    hashes = lambda: {str(path.relative_to(ROOT)): hashlib.sha256(path.read_bytes()).hexdigest() for path in paths}
    report = {"status": "running", "design": design, "seed": seed, "physics_hz": 120, "config": asdict(config),
              "source_before": hashes(), "results": []}
    save = lambda: (output / "summary.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    save()
    try:
        for case in cases:
            result = run_case(case, config, seed, output)
            report["results"].append(result)
            save()
            print(json.dumps({key: value for key, value in result.items() if key not in ("final_estimate", "sensor_config")}), flush=True)
    except (ArithmeticError, AssertionError, ValueError, OSError) as error:
        report.update(status="failed", failed_case=case, error=str(error), not_run=cases[cases.index(case) + 1:])
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
    parser.add_argument("--design", choices=("reference", "gr86"), default="gr86")
    parser.add_argument("--cases", nargs="+", choices=("straight-brake", "turn-brake", "hills"), default=("straight-brake", "turn-brake", "hills"))
    parser.add_argument("--seed", type=int, default=17)
    args = parser.parse_args()
    run(args.output, args.design, args.cases, args.seed)
