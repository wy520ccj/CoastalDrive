"""本批T2续跑：显式前次结果、完整修复模块证据、原始节点集合与改动白名单。"""

import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
from datetime import UTC, datetime

from t2_continue import BASELINE, ROOT
from validate import execute_plan, git_value, make_plan

ALLOWED_TESTS = {
    "tests/test_gr86.py", "tests/test_h1_vehicle.py", "tests/test_h2_map.py",
    "tests/test_phase3_map.py", "tests/test_impact_delivery.py", "tests/test_lab_ui.py",
    "tests/test_physics_cli.py", "tests/test_physics_testbed.py",
    "tests/test_tire_compliance_config.py",
    "tests/test_ui_theme.py",
}


def read(path):
    return json.loads(path.read_text(encoding="utf-8"))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--previous", required=True)
    parser.add_argument("--supplement", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    previous, supplement, output = (ROOT / value for value in
                                    (args.previous, args.supplement, args.output))
    if output.exists():
        raise ValueError("不覆盖已有续跑")
    prior, fixed = read(previous / "summary.json"), read(supplement / "summary.json")
    assert prior["status"] == "failed" and fixed["passed"] is True
    prior_log = (previous / "pytest.log").read_text(encoding="utf-8")
    match = re.search(r"1 failed, (\d+) passed", prior_log)
    assert match is not None
    count = int(match[1])
    changed = git_value("diff", "--name-only", BASELINE, "HEAD").splitlines()
    assert [p for p in changed if p.startswith("src/")] == ["src/ui/parameter_help.py"]
    assert {p for p in changed if p.startswith("tests/")} == ALLOWED_TESTS
    assert [p for p in changed if p.startswith("assets/")] == ["assets/game/vehicle-configs/gr86-2022-premium-6mt.json"]
    collection = subprocess.run([sys.executable, "-m", "pytest", "--collect-only", "-q", "tests"],
        cwd=ROOT, env={**os.environ, "PYTHONUTF8": "1", "PYTHONIOENCODING": "utf-8"},
        capture_output=True, text=True, encoding="utf-8", check=True).stdout
    nodes = [line for line in collection.splitlines() if line.startswith("tests/") and "::" in line]
    assert set(nodes) == set(prior["reused_nodes"] + prior["remaining_nodes"])
    failed = prior["remaining_nodes"][count]
    assert "FAILED " + failed in prior_log
    completed = [node for node in nodes if any(node == target or node.startswith(target + "::")
                                              for target in fixed["tests"])]
    assert failed in completed
    assert re.search(rf"\b{len(completed)} passed\b",
                     (supplement / "pytest.log").read_text(encoding="utf-8"))
    reused_set = set(prior["reused_nodes"] + prior["remaining_nodes"][:count] + completed)
    reused, remaining = [n for n in nodes if n in reused_set], [n for n in nodes if n not in reused_set]
    files = list(dict.fromkeys(n.split("::")[0] for n in remaining))
    assert not any(n.split("::")[0] in files for n in reused)
    checks = make_plan("T2", [], [], output)
    checks[1].args = ["-m", "pytest", "-q", "-x", *files]
    checks = [c for c in checks if not c.name.startswith("headless-") and c.name != "handling"]
    sources = [previous / "summary.json", previous / "pytest.log",
               supplement / "summary.json", supplement / "pytest.log"]
    metadata = {"started_utc": datetime.now(UTC).isoformat(), "git_head": git_value("rev-parse", "HEAD"),
        "git_status": git_value("status", "--short"), "python": sys.version, "baseline": BASELINE,
        "reused_pytest_passes": len(reused), "remaining_pytest_items": len(remaining),
        "reused_nodes": reused, "remaining_nodes": remaining, "reused_checks": prior["reused_checks"],
        "evidence_sha256": {str(p): hashlib.sha256(p.read_bytes()).hexdigest() for p in sources},
        "reuse_basis": "本批生产物理/配置数值保持；此前完成项及修复完整模块逐节点去重，原首败保留；不跳过任何未执行节点，余T2长测实际执行"}
    print(f"REUSE {len(reused)} / RUN {len(remaining)} pytest items", flush=True)
    return execute_plan(checks, output, "T2-continuation", 1800, metadata)


if __name__ == "__main__":
    raise SystemExit(main())
