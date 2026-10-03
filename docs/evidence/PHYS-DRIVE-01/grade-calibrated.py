"""当前两模式完整传动的5°原生坡停，沿用ROT位移/力平衡门槛。"""

import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "tools"))
from physics.rotor_grade import DrivingMode, run_trial

output = Path(sys.argv[1])
output.mkdir(parents=True, exist_ok=False)
hashes = lambda: {p.relative_to(ROOT).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
    for folder in ("src", "tests", "tools") for p in sorted((ROOT / folder).rglob("*.py"))}
before = hashes()
report = {"status": "running", "source_before": before, "trials": [],
    "scope": "current finite drivetrain and continuous reference; 5-degree native support and 10s held brake, no runtime speed/position overrides"}


def save():
    (output / "summary.json").write_text(json.dumps(report, indent=2, allow_nan=False), encoding="utf-8")


save()
try:
    for mode in DrivingMode:
        result = run_trial(mode, True, output / f"{mode.value}.jsonl.gz")
        report["trials"].append(result)
        save()
        print(f"{mode.value} drift={result['displacement_m']:.6g} force={result['mean_longitudinal_force_n']:.6g} passed={result['passed']}", flush=True)
except (ArithmeticError, OSError, ValueError) as error:
    report.update(status="failed", error=repr(error), failed_mode=mode.value)
    save()
    raise
after = hashes()
report.update(status="completed", source_after=after, source_stable=before == after,
              passed=all(trial["passed"] for trial in report["trials"]))
save()
assert before == after
raise SystemExit(0 if report["passed"] else 1)
