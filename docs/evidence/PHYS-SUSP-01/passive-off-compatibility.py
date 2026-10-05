"""从实际基线Git源码独立运行同输入后驱，核对完整车辆快照字节。"""

import gzip
import hashlib
import json
import subprocess
import sys
from dataclasses import asdict, replace
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
EVIDENCE = Path(__file__).resolve().parent / "passive-off-r1"
BASE = "6be5f54"

if len(sys.argv) == 3:
    source, output = map(Path, sys.argv[1:])
    sys.path[:0] = [str(source), str(ROOT / "tools")]
    import vehicle  # 先固定基线模块；研究工具自身会把当前src插到搜索路径前端。
    from driving_modes import DrivingMode
    from physics.reference_ab import _create_vehicle, _step
    from vehicle_state import VehicleCommand

    output.mkdir(parents=True, exist_ok=True)
    for mode in DrivingMode:
        config = mode.vehicle_config
        if source.resolve() == (ROOT / "src").resolve():
            config = replace(config, suspension_coupled_enabled=False)
        world, vehicle = _create_vehicle(config)
        rows = []
        try:
            for tick in range(120):
                command = (VehicleCommand(throttle=.7, direction=1, steering=3.) if tick < 60
                           else VehicleCommand(brake=.5, direction=1) if tick < 90
                           else VehicleCommand(throttle=.5, direction=-1, gear=-1))
                _step(world, vehicle, command)
                rows.append(json.dumps(asdict(vehicle.snapshot()), ensure_ascii=False, allow_nan=False))
        finally:
            vehicle.close()
        with gzip.open(output / (mode.value + ".jsonl.gz"), "wt", encoding="utf-8") as handle:
            handle.write("\n".join(rows) + "\n")
else:
    verify_existing = sys.argv[1:] == ["--verify-existing"]
    source = ROOT / "logs/physics/PHYS-SUSP-01-coupled-baseline-src"
    source.mkdir(parents=True, exist_ok=True)
    files = subprocess.check_output(["git", "ls-tree", "-r", "--name-only", BASE, "src"], cwd=ROOT, text=True).splitlines()
    for name in files:
        if name.endswith(".py"):
            target = source / Path(name).relative_to("src")
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(subprocess.check_output(["git", "show", BASE + ":" + name], cwd=ROOT))
    manifest = {str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest()
                for group in ("src", "tests", "tools") for p in (ROOT / group).rglob("*.py")}
    if not verify_existing:
        for label, directory in (("baseline", source), ("current", ROOT / "src")):
            subprocess.run([sys.executable, str(Path(__file__).resolve()), str(directory), str(EVIDENCE / label)], cwd=ROOT, check=True)
    else:
        frozen = json.loads((EVIDENCE.parent / "passive-handling-r1/summary.json").read_text(encoding="utf-8"))["source_after"]
        assert all(hashlib.sha256((ROOT / name).read_bytes()).hexdigest() == digest for name, digest in frozen.items())
    results = []
    for mode in ("game", "simulation"):
        old = gzip.decompress((EVIDENCE / "baseline" / (mode + ".jsonl.gz")).read_bytes())
        new = gzip.decompress((EVIDENCE / "current" / (mode + ".jsonl.gz")).read_bytes())
        projected_rows = []
        for line in new.decode("utf-8").splitlines(keepends=True):
            state = json.loads(line)
            assert state.pop("suspension_state") is None
            ending = "\r\n" if line.endswith("\r\n") else "\n"
            projected_rows.append(json.dumps(state, ensure_ascii=False, allow_nan=False) + ending)
        projected = "".join(projected_rows).encode("utf-8")
        assert old == projected, mode
        results.append({"mode": mode, "ticks": 120, "identical_common_bytes": True, "current_full_sha256": hashlib.sha256(new).hexdigest(), "common_sha256": hashlib.sha256(projected).hexdigest()})
    assert all(hashlib.sha256((ROOT / name).read_bytes()).hexdigest() == digest for name, digest in manifest.items())
    (EVIDENCE / "compatibility.json").write_text(json.dumps({"base": BASE, "results": results, "source_before": manifest, "source_stable": True, "current_switch": "suspension_coupled_enabled=False", "new_field_projection": ["suspension_state=None"], "verification_reused_existing_raw": verify_existing}, indent=2) + "\n", encoding="utf-8")
    print("Suspension coupled-off: 240 ticks, all prior snapshot fields byte-identical; only new None state projected.")
