"""接续原T2，额外复用已完成的54项道路/H3模块；原失败分别保留。"""

import hashlib
import json
import os
import subprocess
import sys
from datetime import UTC, datetime

from t2_continue import BASELINE, ROOT
from validate import execute_plan, git_value, make_plan


def main():
    output = ROOT / "logs/validation/GAME-GHOST-01-T2-after-routes"
    if output.exists():
        raise ValueError("不覆盖已有续跑")
    prior = ROOT / "logs/validation/GAME-GHOST-01-T2-after-h1"
    routes = ROOT / "logs/validation/VALIDATION-CONTACT-02-T1"
    supplement = ROOT / "logs/validation/VALIDATION-CONTACT-02-T1-supplement"
    prior_summary = json.loads((prior / "summary.json").read_text(encoding="utf-8"))
    assert prior_summary["status"] == "failed" and prior_summary["reused_pytest_passes"] == 686
    assert "1 failed, 2 passed" in (prior / "pytest.log").read_text(encoding="utf-8")
    assert "1 failed, 53 passed" in (routes / "pytest.log").read_text(encoding="utf-8")
    assert "1 passed" in (supplement / "pytest.log").read_text(encoding="utf-8")
    assert json.loads((supplement / "summary.json").read_text(encoding="utf-8"))["passed"] is True
    changed = git_value("diff", "--name-only", BASELINE, "HEAD").splitlines()
    assert [p for p in changed if p.startswith("src/")] == ["src/ui/parameter_help.py"]
    assert [p for p in changed if p.startswith("tests/")] == [
        "tests/test_gr86.py", "tests/test_h1_vehicle.py", "tests/test_h2_map.py", "tests/test_phase3_map.py"]
    assert [p for p in changed if p.startswith("assets/")] == ["assets/game/vehicle-configs/gr86-2022-premium-6mt.json"]
    collection = subprocess.run([sys.executable, "-m", "pytest", "--collect-only", "-q", "tests"],
        cwd=ROOT, env={**os.environ, "PYTHONUTF8": "1", "PYTHONIOENCODING": "utf-8"},
        capture_output=True, text=True, encoding="utf-8", check=True).stdout
    nodes = [line for line in collection.splitlines() if line.startswith("tests/") and "::" in line]
    assert set(nodes) == set(prior_summary["reused_nodes"] + prior_summary["remaining_nodes"])
    modules = ("tests/test_h2_map.py::", "tests/test_h3_review.py::", "tests/test_phase3_map.py::")
    completed = [n for n in nodes if n.startswith(modules)]
    assert len(completed) == 54
    reused_set = set(prior_summary["reused_nodes"] + completed)
    reused, remaining = [n for n in nodes if n in reused_set], [n for n in nodes if n not in reused_set]
    assert len(reused) == 740 and len(remaining) == 2776
    files = list(dict.fromkeys(n.split("::")[0] for n in remaining))
    checks = make_plan("T2", [], [], output)
    checks[1].args = ["-m", "pytest", "-q", "-x", *files]
    checks = [c for c in checks if not c.name.startswith("headless-") and c.name != "handling"]
    sources = [prior / "summary.json", prior / "pytest.log", routes / "summary.json", routes / "pytest.log",
               supplement / "summary.json", supplement / "pytest.log"]
    metadata = {"started_utc": datetime.now(UTC).isoformat(),
        "git_head": git_value("rev-parse", "HEAD"), "git_status": git_value("status", "--short"),
        "python": sys.version, "baseline": BASELINE, "reused_pytest_passes": len(reused),
        "remaining_pytest_items": len(remaining), "reused_nodes": reused, "remaining_nodes": remaining,
        "evidence_sha256": {str(p): hashlib.sha256(p.read_bytes()).hexdigest() for p in sources},
        "reused_checks": prior_summary["reused_checks"],
        "reuse_basis": "此前686项+完整道路/H3模块54项，交通原生分支恢复原断言后单独通过；只改接触读取，生产物理不变；三种子/handling同源复用；余交通/道路长测实际执行"}
    return execute_plan(checks, output, "T2-continuation", 1800, metadata)


if __name__ == "__main__":
    raise SystemExit(main())
