"""倾斜起始车姿产生真实异步落地；不在运行中修改接触或轮速。"""

import gzip
import hashlib
import json
import sys
from dataclasses import asdict, replace
from pathlib import Path

from panda3d.core import TransformState, Vec3

ROOT = Path(__file__).resolve().parents[3]
OUT = Path(__file__).resolve().parent / "single-wheel-recontact-r1"
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
        config = replace(mode.vehicle_config, front_drive_share=share)
        world, vehicle = _create_vehicle(config)
        rows = []
        try:
            vehicle._chassis.setTransform(TransformState.makePosHpr(Vec3(0., 0., 1.2), Vec3(0., 4., 8.)))
            previous = (False,) * 4
            recontacts = [0] * 4
            single = []
            for tick in range(300):
                _step(world, vehicle, VehicleCommand(throttle=.7, direction=1))
                state = vehicle.snapshot()
                support = tuple(w.sample_support for w in state.wheel_dynamics)
                if support.count(False) == 1:
                    single.append(tick + 1)
                for i, supported in enumerate(support):
                    recontacts[i] += int(supported and not previous[i])
                previous = support
                assert all(w.force_residual < .001 for w in state.wheel_dynamics)
                rows.append({"tick": tick + 1, "car": asdict(state)})
            name = f"{mode.value}-{layout}.jsonl.gz"
            with gzip.open(OUT / name, "wt", encoding="utf-8") as stream:
                for row in rows:
                    stream.write(json.dumps(row, ensure_ascii=False, allow_nan=False) + "\n")
            result = {"mode": mode.value, "layout": layout, "config": asdict(config),
                      "single_wheel_unsupported_ticks": single, "recontact_counts": recontacts,
                      "trace": name, "initial_pose": {"position": [0., 0., 1.2], "hpr": [0., 4., 8.]}}
            results.append(result)
            (OUT / "progress.json").write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
            assert single and all(recontacts)
            print(mode.value, layout, "single-wheel ticks", len(single), "recontacts", recontacts, flush=True)
        finally:
            vehicle.close()
assert all(hashlib.sha256((ROOT / p).read_bytes()).hexdigest() == h for p, h in source.items())
(OUT / "summary.json").write_text(json.dumps({"status": "completed", "source_stable": True,
    "source_before": source, "ticks_per_case": 300, "results": results}, ensure_ascii=False, indent=2), encoding="utf-8")
