"""固定部件标定轮荷与旧质量基准的轮胎曲线/完整车制动A/B。"""

import argparse
import csv
import hashlib
import json
import math
import sys
from dataclasses import asdict, replace
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from panda3d.core import Vec3

from driving_experiment import DrivingExperiment, ExperimentOptions
from lab_records import model_fingerprint
from tire_forces import tire_force
from tire_properties import tire_grip, tire_stiffness
from vehicle_designs import REFERENCE_DESIGN
from vehicle_state import FIXED_DT, VehicleCommand


def braking(config, path):
    experiment = DrivingExperiment(config, ExperimentOptions(track="lab"))
    simulation = experiment.simulation
    neutral = VehicleCommand(gear=0, clutch=0.)
    try:
        simulation.settle_initial()
        for _ in range(math.ceil(8 * config.braking.response_time / FIXED_DT)):
            simulation.step(neutral)
        car = simulation.player
        forward = car._chassis.getTransform().getQuat().getForward()
        car._chassis.setLinearVelocity(Vec3(forward * (100 / 3.6)))
        car.tires.initialize_rolling(100 / 3.6)
        car.powertrain.initialize_rolling(100 / 3.6)
        previous = simulation.snapshot()
        distance = 0.
        rows = []
        maximum_force_residual = 0.
        for tick in range(1, 1441):
            simulation.step(VehicleCommand(brake=1., gear=0, clutch=0.))
            state = simulation.snapshot()
            distance += math.dist(previous.player.position[:2], state.player.position[:2])
            rows.append({"time": tick * FIXED_DT, "speed_kph": state.player.speed * 3.6,
                         "distance_m": distance, "ax": state.player.acceleration,
                         **{f"{key}_{i}": value for i, wheel in enumerate(state.player.wheel_dynamics)
                            for key, value in (("load", wheel.normal_load), ("grip", wheel.force_grip),
                                               ("cx", wheel.force_longitudinal_stiffness),
                                               ("cy", wheel.force_lateral_stiffness))}})
            assert state.collisions == 0
            assert len(state.player.wheel_contacts) == 4
            assert all(contact.in_contact for contact in state.player.wheel_contacts)
            for index, wheel in enumerate(state.player.wheel_dynamics):
                # 数值力与满足预算的本构目标之间有已发布残差，按其分量上界核对。
                maximum_force_residual = max(maximum_force_residual, wheel.force_residual)
                assert math.hypot(wheel.fx, wheel.fy) <= wheel.force_grip + math.sqrt(2) * wheel.force_residual + 1e-7, (
                    tick, index, wheel.force_mode, wheel.fx, wheel.fy,
                    wheel.force_grip, wheel.normal_load, wheel.force_residual)
            previous = state
            if state.player.speed < .1:
                break
        else:
            raise RuntimeError("12秒内未停止")
        with path.open("w", encoding="utf-8", newline="") as stream:
            writer = csv.DictWriter(stream, fieldnames=rows[0])
            writer.writeheader()
            writer.writerows(rows)
        return {"distance_m": distance, "simulation_seconds": tick * FIXED_DT,
                "samples": len(rows), "maximum_force_residual_N": maximum_force_residual,
                "trace_sha256": hashlib.sha256(path.read_bytes()).hexdigest()}
    finally:
        experiment.close()


def run(output):
    output.mkdir(parents=True, exist_ok=False)
    before = model_fingerprint()
    base = REFERENCE_DESIGN
    loaded = replace(base, mass=1500., road_friction=.6,
                     body_inertia=tuple(value * 1500 / base.mass for value in base.body_inertia))
    legacy = replace(loaded, tire_reference_load=loaded.mass * 9.81 / 4)
    results = {}
    curves = []
    for label, config in (("mass_based_A", legacy), ("fixed_tire_B", loaded)):
        for load in (1000., 2000., 2943., 3678.75, 5000., 6000.):
            cx, cy = tire_stiffness(load, config)
            for kappa, alpha in ((.0001, 0.), (.12, 0.), (0., .0001), (0., .1), (.12, .1)):
                fx, fy = tire_force(kappa, alpha, load, config.road_friction, config)
                curves.append({"case": label, "load_N": load, "kappa": kappa, "alpha_rad": alpha,
                               "grip_N": tire_grip(load, config.road_friction, config), "cx_N": cx, "cy_N_rad": cy,
                               "fx_N": fx, "fy_N": fy})
        results[label] = {"config": asdict(config), **braking(config, output / f"{label}-braking.csv")}
    with (output / "tire-curves.csv").open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=curves[0])
        writer.writeheader()
        writer.writerows(curves)
    after = model_fingerprint()
    assert before == after
    assert results["fixed_tire_B"]["distance_m"] > results["mass_based_A"]["distance_m"]
    results["protocol"] = "同一1500kg设计车/同比惯量/100km/h/μ0.6/120Hz两子步；仅轮胎固定基准不同。不是点载荷装载或实车标定，A用新方程中等价旧归一化值。"
    results["source_before"] = before
    results["source_stable"] = True
    (output / "summary.json").write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({name: {key: row[key] for key in ("distance_m", "simulation_seconds")}
                      for name, row in results.items() if name.endswith(("_A", "_B"))}))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    run(args.output.resolve())
