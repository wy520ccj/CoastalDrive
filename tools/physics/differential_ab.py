"""两模式三布局的有限粘性限滑A/B；相同初值/控制，仅限滑硬件不同。"""

import argparse
import gzip
import hashlib
import json
import math
import sys
from dataclasses import asdict, replace
from pathlib import Path

from panda3d.core import TransformState, Vec3

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT / "src"), str(ROOT / "tools")]
from physics.esc_probe import command_at
from physics.reference_ab import _create_vehicle, _step

from driving_modes import DrivingMode
from vehicle_state import FIXED_DT, VehicleCommand

CASES = ("split-mu-launch", "steering-step", "single-wheel-recontact", "reverse", "engine-braking")
LAYOUTS = {"RWD": 0., "FWD": 1., "AWD": .5}


def run_trial(config, case, duration, output):
    world, car = _create_vehicle(config)
    rows, single, recontacts = [], 0, [0] * 4
    heat, slip_integral, torque_maximum = [0.] * 3, [0.] * 3, [0.] * 3
    try:
        if case == "single-wheel-recontact":
            car._chassis.setTransform(TransformState.makePosHpr(Vec3(0., 0., 1.2), Vec3(0., 4., 8.)))
        else:
            for _ in range(240):
                _step(world, car, VehicleCommand())
        if case == "split-mu-launch":
            car.on_asphalt = lambda x, _y: x < 0
        speed = 80 / 3.6 if case == "steering-step" else 12. if case == "engine-braking" else 0.
        car._chassis.setLinearVelocity(Vec3(0., speed, 0.))
        car.tires.initialize_rolling(speed)
        previous_support = tuple(w.sample_support for w in car.snapshot().wheel_dynamics)
        maximum = 0.
        for tick in range(round(duration / FIXED_DT)):
            if case == "steering-step":
                _phase, command = command_at(case, tick * FIXED_DT)
            elif case == "engine-braking":
                command = VehicleCommand(gear=1, clutch=1.)
            else:
                command = VehicleCommand(throttle=1., direction=-1 if case == "reverse" else 1)
            _step(world, car, command)
            state = car.snapshot()
            train = state.powertrain_state
            support = tuple(w.sample_support for w in state.wheel_dynamics)
            single += int(support.count(False) == 1)
            for i in range(4):
                recontacts[i] += int(support[i] and not previous_support[i])
            previous_support = support
            for i in range(3):
                assert train.differential_heat[i] >= 0.
                assert abs(train.differential_torques[i]) <= config.differential_capacity[i] + 1e-11
                heat[i] += train.differential_heat[i]
                slip_integral[i] += abs(train.differential_slips[i]) * FIXED_DT
                torque_maximum[i] = max(torque_maximum[i], abs(train.differential_torques[i]))
            maximum = max(maximum, *(w.force_residual for w in state.wheel_dynamics))
            assert maximum < .001
            rows.append({"tick": tick + 1, "input": asdict(command), "car": asdict(state)})
        with gzip.open(output, "wt", encoding="utf-8") as stream:
            for row in rows:
                stream.write(json.dumps(row, ensure_ascii=False, allow_nan=False) + "\n")
        if case == "single-wheel-recontact":
            assert single > 0 and all(recontacts)
        return {"config": asdict(config), "ticks": len(rows), "end_signed_speed": car.signed_speed(),
                "end_horizontal_speed": math.hypot(*state.velocity[:2]), "heat_j": heat,
                "absolute_slip_integral_rad": slip_integral, "maximum_torques_nm": torque_maximum,
                "single_wheel_unsupported_ticks": single, "recontact_counts": recontacts,
                "max_force_residual": maximum, "trace": output.name}
    except (ArithmeticError, AssertionError) as error:
        with gzip.open(output.with_name(output.stem + "-partial.gz"), "wt", encoding="utf-8") as stream:
            for row in rows:
                stream.write(json.dumps(row, ensure_ascii=False, allow_nan=False) + "\n")
        output.with_name(output.stem + "-failure.json").write_text(json.dumps({
            "error": repr(error), "completed_ticks": len(rows), "case": case,
            "config": asdict(config)}, ensure_ascii=False, indent=2), encoding="utf-8")
        raise
    finally:
        car.close()


def run_matrix(output, duration=4., cases=CASES, modes=("game", "simulation"), layouts=tuple(LAYOUTS)):
    output.mkdir(parents=True, exist_ok=False)

    def hashes():
        return {p.relative_to(ROOT).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
                for group in ("src", "tests", "tools") for p in sorted((ROOT / group).rglob("*.py"))}

    before, results = hashes(), []
    pending = [(mode, layout, case, enabled) for mode in modes for layout in layouts for case in cases for enabled in (False, True)]
    report = {"status": "running", "source_before": before, "results": results,
              "protocol": {"duration_s": duration, "frequency_hz": 120, "stride": 1,
                           "damping": "enabled driven axles and AWD center: 20 Nms/rad", "capacity": "80 Nm per enabled port",
                           "tcs": "off in both arms to isolate mechanical coupling; ABS/ESC same mode defaults",
                           "initialization": "only before first tick; native gravity/contact thereafter",
                           "claim": "finite viscous design mechanism; not measured clutch LSD, shaft inertia, human or performance gate"}}

    def save():
        (output / "summary.json").write_text(json.dumps(report, ensure_ascii=False, indent=2, allow_nan=False), encoding="utf-8")

    save()
    try:
        for mode in modes:
            for layout in layouts:
                share = LAYOUTS[layout]
                base = DrivingMode(mode).vehicle_config
                for case in cases:
                    pair = {"mode": mode, "layout": layout, "case": case}
                    results.append(pair)
                    for enabled in (False, True):
                        damping = (20. if enabled and share else 0., 20. if enabled and share < 1 else 0.,
                                   20. if enabled and 0 < share < 1 else 0.)
                        config = replace(base, front_drive_share=share, differential_damping=damping,
                            differential_capacity=tuple(80. if c else 0. for c in damping), grass_friction=.2,
                            traction=replace(base.traction, tcs_enabled=False))
                        filename = f"{mode}-{layout}-{case}-{'on' if enabled else 'off'}.jsonl.gz"
                        result = run_trial(config, case, duration, output / filename)
                        pair["on" if enabled else "off"] = result
                        pending.remove((mode, layout, case, enabled))
                        save()
                        print(f"DONE {mode}/{layout}/{case}/{enabled} speed={result['end_signed_speed']:.4f}", flush=True)
                    pair["speed_on_minus_off"] = pair["on"]["end_signed_speed"] - pair["off"]["end_signed_speed"]
    except (ArithmeticError, AssertionError, ValueError, OSError) as error:
        report.update(status="failed", error=repr(error), failed_trial=pending[0], not_run=pending[1:])
        save()
        raise
    after = hashes()
    report.update(status="completed", source_after=after, source_stable=before == after)
    save()
    assert before == after
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--duration", type=float, default=4.)
    parser.add_argument("--cases", nargs="+", choices=CASES, default=CASES)
    parser.add_argument("--modes", nargs="+", choices=("game", "simulation"), default=["game", "simulation"])
    parser.add_argument("--layouts", nargs="+", choices=LAYOUTS, default=list(LAYOUTS))
    args = parser.parse_args()
    run_matrix(args.output, args.duration, args.cases, args.modes, args.layouts)
