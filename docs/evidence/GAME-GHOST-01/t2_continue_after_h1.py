"""接续原T2：显式复用667+9+H1十项及相同版本启动/动力学检查。"""

import hashlib
import json
import os
import subprocess
import sys
from datetime import UTC, datetime

from t2_continue import BASELINE, FAILED, ROOT
from validate import execute_plan, git_value, make_plan


def main():
    output = ROOT / "logs/validation/GAME-GHOST-01-T2-after-h1"
    if output.exists():
        raise ValueError("不覆盖已有续跑")
    previous = ROOT / "logs/validation/GAME-GHOST-01-T2-continuation"
    h1 = ROOT / "logs/validation/VALIDATION-CONTACT-01-T1"
    handling = ROOT / "logs/VALIDATION-CONTACT-01/handling/handling.json"
    original = ROOT / "logs/validation/GAME-GHOST-01-T2"
    previous_summary = json.loads((previous / "summary.json").read_text(encoding="utf-8"))
    assert previous_summary["status"] == "failed" and previous_summary["reused_pytest_passes"] == 667
    assert "1 failed, 9 passed" in (previous / "pytest.log").read_text(encoding="utf-8")
    assert "FAILED tests/test_h1_vehicle.py::test_idle_car_has_four_ground_contacts_and_can_start" in (previous / "pytest.log").read_text(encoding="utf-8")
    h1_summary = json.loads((h1 / "summary.json").read_text(encoding="utf-8"))
    assert h1_summary["passed"] is True
    assert "10 passed" in (h1 / "pytest.log").read_text(encoding="utf-8")
    assert json.loads(handling.read_text(encoding="utf-8"))["passed"] is True
    changed = git_value("diff", "--name-only", BASELINE, "HEAD").splitlines()
    assert [p for p in changed if p.startswith("src/")] == ["src/ui/parameter_help.py"]
    assert [p for p in changed if p.startswith("tests/")] == ["tests/test_gr86.py", "tests/test_h1_vehicle.py"]
    assert [p for p in changed if p.startswith("assets/")] == ["assets/game/vehicle-configs/gr86-2022-premium-6mt.json"]
    collection = subprocess.run([sys.executable, "-m", "pytest", "--collect-only", "-q", "tests"],
        cwd=ROOT, env={**os.environ, "PYTHONUTF8": "1", "PYTHONIOENCODING": "utf-8"},
        capture_output=True, text=True, encoding="utf-8", check=True).stdout
    nodes = [line for line in collection.splitlines() if line.startswith("tests/") and "::" in line]
    assert nodes.index(FAILED) == 667 and nodes[:667] == previous_summary["reused_nodes"]
    assert nodes[667:] == previous_summary["remaining_nodes"]
    assert len([n for n in nodes if n.startswith("tests/test_h1_vehicle.py::")]) == 10
    reused = nodes[:676] + [n for n in nodes if n.startswith("tests/test_h1_vehicle.py::")]
    remaining = [n for n in nodes if n not in set(reused)]
    assert len(reused) == 686 and len(remaining) == 2830
    files = list(dict.fromkeys(n.split("::")[0] for n in remaining))
    checks = make_plan("T2", [], [], output)
    checks[1].args = ["-m", "pytest", "-q", "-x", *files]
    reused_checks = [c for c in checks if c.name.startswith("headless-") or c.name == "handling"]
    checks = [c for c in checks if c not in reused_checks]
    sources = [original / "summary.json", original / "pytest.log", previous / "summary.json",
               previous / "pytest.log", h1 / "summary.json", h1 / "pytest.log", handling]
    metadata = {"started_utc": datetime.now(UTC).isoformat(),
        "git_head": git_value("rev-parse", "HEAD"), "git_status": git_value("status", "--short"),
        "python": sys.version, "baseline": BASELINE, "reused_pytest_passes": len(reused),
        "remaining_pytest_items": len(remaining), "reused_nodes": reused, "remaining_nodes": remaining,
        "evidence_sha256": {str(p): hashlib.sha256(p.read_bytes()).hexdigest() for p in sources},
        "reused_checks": [{"name": c.name, "source": str(handling if c.name == "handling" else h1 / "summary.json")}
                          for c in reused_checks],
        "reuse_basis": "667未改测试+前次续跑9项+完整H1十项；仅验收读取改为实际快照，物理/参数未改；同版三种子和完整handling已实际通过；所有交通/道路长测仍执行"}
    return execute_plan(checks, output, "T2-continuation", 1800, metadata)


if __name__ == "__main__":
    raise SystemExit(main())
