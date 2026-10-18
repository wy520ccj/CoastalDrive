"""仅用于250be45整批T2在GR86首败后的有据续跑。"""

import hashlib
import json
import os
import re
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "tools"))
from validate import execute_plan, git_value, make_plan

BASELINE = "250be4571d3fb49ff95d2ef83de850ea24558dcd"
FAILED = "tests/test_gr86.py::test_source_fields_and_exact_rating_anchors"


def main():
    original = ROOT / "logs/validation/GAME-GHOST-01-T2"
    output = ROOT / "logs/validation/GAME-GHOST-01-T2-continuation"
    if output.exists():
        raise ValueError("不覆盖已有续跑")
    summary = json.loads((original / "summary.json").read_text(encoding="utf-8"))
    log = (original / "pytest.log").read_text(encoding="utf-8")
    assert summary["git_head"] == BASELINE and summary["git_status"] == ""
    assert summary["checks"][1]["status"] == "failed"
    assert "1 failed, 667 passed" in log and "FAILED " + FAILED in log
    changed = git_value("diff", "--name-only", BASELINE, "HEAD").splitlines()
    assert [name for name in changed if name.startswith("src/")] == ["src/ui/parameter_help.py"]
    assert [name for name in changed if name.startswith("tests/")] == ["tests/test_gr86.py"]
    assert [name for name in changed if name.startswith("assets/")] == [
        "assets/game/vehicle-configs/gr86-2022-premium-6mt.json"]
    env = {**os.environ, "PYTHONUTF8": "1", "PYTHONIOENCODING": "utf-8"}
    collection = subprocess.run([sys.executable, "-m", "pytest", "--collect-only", "-q", "tests"],
        cwd=ROOT, env=env, capture_output=True, text=True, encoding="utf-8", check=True).stdout
    nodes = [line for line in collection.splitlines() if line.startswith("tests/") and "::" in line]
    assert nodes.index(FAILED) == 667
    prefix, remainder = nodes[:667], nodes[667:]
    old_files = list(dict.fromkeys(node.split("::")[0] for node in prefix))
    files = list(dict.fromkeys(node.split("::")[0] for node in remainder))
    assert not set(old_files) & set(files)
    assert not set(old_files) & set(changed)
    checks = make_plan("T2", [], [], output)
    checks[1].args = ["-m", "pytest", "-q", "-x", *files]
    assert len(subprocess.list2cmdline([sys.executable, *checks[1].args])) < 30000
    metadata = {"started_utc": datetime.now(UTC).isoformat(),
        "git_head": git_value("rev-parse", "HEAD"), "git_status": git_value("status", "--short"),
        "python": sys.version, "original_run": str(original), "baseline": BASELINE,
        "reused_pytest_passes": len(prefix), "remaining_pytest_items": len(remainder),
        "reuse_basis": "此前667项测试文件未改；物理源码/扩展未改；仅F1来源显示与GR86元数据，完整实际配置SHA保持；受影响处普通T1/Double短测已补验",
        "original_summary_sha256": hashlib.sha256((original / "summary.json").read_bytes()).hexdigest(),
        "reused_nodes": prefix, "remaining_nodes": remainder,
        "collected_total": int(re.search(r"(\d+) tests collected", collection)[1])}
    return execute_plan(checks, output, "T2-continuation", 1800, metadata)


if __name__ == "__main__":
    raise SystemExit(main())
