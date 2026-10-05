"""SI硬件与旧归一化硬件的真实质量对照；完整固定步快照保存。"""

import argparse
import gzip
import hashlib
import json
import sys
from dataclasses import asdict, replace
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT / "src"), str(ROOT / "tools")]
from panda3d.bullet import getBulletVersion
from physics.reference_ab import _create_vehicle, _step

from driving_modes import DrivingMode
from vehicle_state import VehicleCommand


def run_trial(mode, mass, enabled, ticks=240):
    base = DrivingMode(mode).vehicle_config
    inertia = tuple(value * mass / base.mass for value in base.body_inertia) if base.body_inertia else None
    config = replace(base, mass=mass, body_inertia=inertia, suspension_si_enabled=enabled)
    world, car = _create_vehicle(config)
    rows = []
    try:
        for tick in range(ticks):
            _step(world, car, VehicleCommand(gear=0))
            state = car.snapshot()
            raw = []
            for i, wheel in enumerate(car._vehicle.getWheels()):
                ray = wheel.getRaycastInfo()
                speed = wheel.getSuspensionRelativeVelocity()
                k = config.suspension_spring_rates[i] if enabled else mass * config.suspension_stiffness
                c = ((config.suspension_compression_damping[i] if speed < 0 else config.suspension_extension_damping[i])
                     if enabled else mass * (config.suspension_compression if speed < 0 else config.suspension_relaxation))
                factor = 1 / max(.1, -ray.getContactNormalWs().dot(ray.getWheelDirectionWs()))
                predicted = max(0., k * state.wheel_contacts[i].compression * factor - c * speed) if ray.isInContact() else 0.
                raw.append({"spring_n_per_m": k, "damping_n_s_per_m": c, "relative_speed": speed,
                            "contact_factor": factor, "predicted_raw_force": predicted,
                            "native_raw_force": wheel.getWheelsSuspensionForce() if ray.isInContact() else 0.,
                            "residual_n": abs(predicted - state.wheel_contacts[i].suspension_force)})
            rows.append({"tick": tick + 1, "car": asdict(state), "native_suspension": raw})
        end = rows[-60:]
        compression = sum(w["compression"] for row in end for w in row["car"]["wheel_contacts"]) / (4 * len(end))
        load = sum(sum(w["normal_load"] for w in row["car"]["wheel_contacts"]) for row in end) / len(end)
        k = config.suspension_spring_rates[0] if enabled else mass * config.suspension_stiffness
        expected = mass * 9.81 / (4 * k)
        residual = max(w["residual_n"] for row in rows for w in row["native_suspension"])
        assert abs(compression - expected) < .001
        assert abs(load - mass * 9.81) < .01 * mass * 9.81
        assert residual < .01
        return {"mode": mode, "mass": mass, "si_enabled": enabled, "config": asdict(config), "ticks": ticks,
                "mean_end_compression_m": compression, "expected_static_compression_m": expected,
                "mean_end_normal_load_n": load, "max_force_formula_residual_n": residual}, rows
    finally:
        car.close()


def run_matrix(output):
    output.mkdir(parents=True, exist_ok=False)
    hashes = lambda: {p.relative_to(ROOT).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
        for group in ("src", "tests", "tools") for p in sorted((ROOT / group).rglob("*.py"))}
    pending = [(mode, mass, enabled) for mode in ("game", "simulation") for mass in (1200., 1800.) for enabled in (False, True)]
    report = {"status": "running", "bullet_version": getBulletVersion(), "source_before": hashes(), "results": [],
              "protocol": "240 native 120 Hz ticks each; neutral, no velocity reset; body inertia scales with mass; unchanged hardware except explicit SI/legacy selection; flat-plane mapping only"}
    try:
        for mode, mass, enabled in list(pending):
            summary, rows = run_trial(mode, mass, enabled)
            name = f"{mode}-{int(mass)}-{'si' if enabled else 'legacy'}.jsonl.gz"
            with gzip.open(output / name, "wt", encoding="utf-8") as stream:
                for row in rows:
                    stream.write(json.dumps(row, ensure_ascii=False, allow_nan=False) + "\n")
            report["results"].append({**summary, "trace": name})
            pending.remove((mode, mass, enabled))
            print(f"DONE {name}: compression {summary['mean_end_compression_m']:.8f} m", flush=True)
    except (ArithmeticError, AssertionError, ValueError, OSError) as error:
        report.update(status="failed", error=repr(error), failed_trial=pending[0], not_run=pending[1:])
        (output / "summary.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
        raise
    after = hashes()
    report.update(status="completed", source_after=after, source_stable=report["source_before"] == after)
    (output / "summary.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    assert report["source_stable"]


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    run_matrix(parser.parse_args().output)
