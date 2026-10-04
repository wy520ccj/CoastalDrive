"""同车低附着起步的TCS开关对照；三布局、两模式走实际执行器。"""

import gzip
import hashlib
import json
import sys
from dataclasses import asdict, replace
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
OUT = Path(__file__).resolve().parent / "control-pairs-r1"
sys.path[:0] = [str(ROOT / "src"), str(ROOT / "tools")]
from physics.reference_ab import _create_vehicle, _step
from driving_modes import DrivingMode
from vehicle_state import VehicleCommand

OUT.mkdir(exist_ok=False)
source = {p.relative_to(ROOT).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
          for folder in ("src", "tests", "tools") for p in (ROOT / folder).rglob("*.py")}
results = []
for mode in DrivingMode:
    for layout, share in (("RWD", 0.), ("FWD", 1.), ("AWD", .5)):
        for enabled in (False, True):
            base = mode.vehicle_config
            config = replace(base, front_drive_share=share, road_friction=.3,
                             traction=replace(base.traction, tcs_enabled=enabled))
            world, vehicle = _create_vehicle(config)
            rows, active, requests, maximum = [], 0, [0.] * 4, 0.
            try:
                for _ in range(240):
                    _step(world, vehicle, VehicleCommand())
                for tick in range(240):
                    _step(world, vehicle, VehicleCommand(throttle=1., direction=1))
                    state = vehicle.snapshot()
                    active += int(state.traction_state.active)
                    for i, request in enumerate(state.traction_state.brake_requests):
                        if i not in config.driven_wheels or not enabled:
                            assert request == 0.
                        requests[i] = max(requests[i], request)
                    maximum = max(maximum, *(w.force_residual for w in state.wheel_dynamics))
                    rows.append({"tick": tick + 1, "car": asdict(state)})
                assert maximum < .001
                assert active > 0 if enabled else active == 0
                name = f"{mode.value}-{layout}-tcs-{enabled}.jsonl.gz"
                with gzip.open(OUT / name, "wt", encoding="utf-8") as stream:
                    for row in rows:
                        stream.write(json.dumps(row, ensure_ascii=False, allow_nan=False) + "\n")
                results.append({"mode": mode.value, "layout": layout, "config": asdict(config),
                                "tcs_enabled": enabled, "active_ticks": active, "maximum_requests": requests,
                                "end_speed": vehicle.signed_speed(), "max_force_residual": maximum, "trace": name})
                (OUT / "progress.json").write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
                print(mode.value, layout, enabled, active, flush=True)
            finally:
                vehicle.close()
assert all(hashlib.sha256((ROOT / p).read_bytes()).hexdigest() == h for p, h in source.items())
(OUT / "summary.json").write_text(json.dumps({"status": "completed", "source_before": source,
    "source_stable": True, "duration_s": 2., "results": results}, ensure_ascii=False, indent=2), encoding="utf-8")
