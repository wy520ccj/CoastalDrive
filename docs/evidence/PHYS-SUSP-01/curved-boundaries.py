"""复用冻结原生原始快照；只核对本次改动的关闭分支与两模式海岸短集成。"""
import gzip
import hashlib
import json
import sys
from dataclasses import asdict, replace
from pathlib import Path

root = Path.cwd()
sys.path[:0] = [str(root / "src"), str(root / "tools")]
from driving_modes import DrivingMode
from physics.reference_ab import _create_vehicle, _step
from simulation import Simulation
from vehicle_state import VehicleCommand

output = root / "docs/evidence/PHYS-SUSP-01/curved-boundaries-r1"
output.mkdir(parents=True, exist_ok=False)
hashes = lambda: {p.relative_to(root).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
                  for group in ("src", "tests", "tools") for p in sorted((root / group).rglob("*.py"))}
report = {"status": "running", "source_before": hashes(), "off": [], "coastal": []}
try:
    for mode in DrivingMode:
        world, car = _create_vehicle(replace(mode.vehicle_config, suspension_coupled_enabled=False))
        rows = []
        try:
            for tick in range(120):
                command = (VehicleCommand(throttle=.7, direction=1, steering=3.) if tick < 60
                           else VehicleCommand(brake=.5, direction=1) if tick < 90
                           else VehicleCommand(throttle=.5, direction=-1, gear=-1))
                _step(world, car, command, world_substeps=1)
                rows.append(asdict(car.snapshot()))
        finally:
            car.close()
        with gzip.open(output / (mode.value + "-off.jsonl.gz"), "wt", encoding="utf-8") as stream:
            stream.write("\n".join(json.dumps(row, ensure_ascii=False, allow_nan=False) for row in rows) + "\n")
        baseline_path = root / "docs/evidence/PHYS-SUSP-01/joint-off-r1/baseline" / (mode.value + ".jsonl.gz")
        raw = gzip.decompress(baseline_path.read_bytes())
        ending = "\r\n" if b"\r\n" in raw else "\n"
        projected = []
        for row in rows:
            assert row.pop("suspension_state") is None
            projected.append(json.dumps(row, ensure_ascii=False, allow_nan=False))
        assert (ending.join(projected) + ending).encode("utf-8") == raw
        report["off"].append({"mode": mode.value, "outer_ticks": 120, "native_steps": 120,
                              "baseline": "6be5f54", "baseline_trace": baseline_path.relative_to(root).as_posix(),
                              "baseline_sha256": hashlib.sha256(baseline_path.read_bytes()).hexdigest(),
                              "common_bytes_identical": True, "projection": "suspension_state=None"})
        sim = Simulation(track="coastal", traffic_count=0, config=mode.vehicle_config, input_config=mode.input_config)
        coast = []
        try:
            for tick in range(120):
                sim.step(VehicleCommand(throttle=.4, gear=1))
                coast.append(asdict(sim.snapshot()))
        finally:
            sim.close()
        with gzip.open(output / (mode.value + "-coastal.jsonl.gz"), "wt", encoding="utf-8") as stream:
            stream.write("\n".join(json.dumps(row, ensure_ascii=False, allow_nan=False) for row in coast) + "\n")
        report["coastal"].append({"mode": mode.value, "outer_ticks": 120, "native_steps": 240,
                                  "last_position": coast[-1]["player"]["position"]})
        print(mode.value, "off common bytes identical; coastal completed", flush=True)
except (AssertionError, ArithmeticError, OSError, ValueError) as error:
    report.update(status="failed", error=repr(error))
    raise
else:
    report["status"] = "completed"
finally:
    report["source_after"] = hashes()
    report["source_stable"] = report["source_before"] == report["source_after"]
    (output / "summary.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")


