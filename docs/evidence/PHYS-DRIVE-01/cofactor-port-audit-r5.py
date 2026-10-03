"""独立进程原型核对既有端口/联合守恒台架，未修改生产源码。"""

import hashlib
import json
from pathlib import Path
import runpy
import sys

EVIDENCE = Path(__file__).resolve().parent
ROOT = EVIDENCE.parents[2]
sys.path.insert(0, str(ROOT / "src"))

import pytest
import tire_drivetrain
import transmission_ports


def main():
    algorithm = EVIDENCE / "cofactor-reuse-audit-r5.py"
    functions = runpy.run_path(str(algorithm))

    def reuse(response, capacity, brake_capacity, efficiency):
        return functions["reused_plans"](response, capacity, brake_capacity, efficiency)[0]

    source = {path.relative_to(ROOT).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest()
              for folder in ("src", "tests", "tools") for path in sorted((ROOT / folder).rglob("*.py"))}
    transmission_ports.clutch_brake_plans = reuse
    tire_drivetrain.clutch_brake_plans = reuse
    args = ["-q", "tests/test_transmission_ports.py", "tests/test_tire_drivetrain.py",
            "--junitxml=docs/evidence/PHYS-DRIVE-01/cofactor-port-audit-r5.junit.xml"]
    exit_code = pytest.main(args)
    source_after = {path: hashlib.sha256((ROOT / path).read_bytes()).hexdigest() for path in source}
    stable = source == source_after
    (EVIDENCE / "cofactor-port-audit-r5.json").write_text(json.dumps(
        {"scope": "isolated prototype, existing independent port and coupled mechanics tests; not full T1/T2",
         "status": "completed", "pytest_exit_code": int(exit_code), "source_stable": stable,
         "algorithm_script_sha256": hashlib.sha256(algorithm.read_bytes()).hexdigest(),
         "runner_script_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
         "pytest_args": args, "source_before": source, "source_after": source_after},
        ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    assert stable
    raise SystemExit(exit_code)


if __name__ == "__main__":
    main()
