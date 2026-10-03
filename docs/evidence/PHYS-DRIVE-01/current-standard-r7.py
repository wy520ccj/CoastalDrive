"""冻结r7的两模式完整标准A/B与坡停；与后台T2独立记账。"""

import hashlib
import json
from pathlib import Path
import runpy
import sys

EVIDENCE = Path(__file__).resolve().parent
ROOT = EVIDENCE.parents[2]


def main():
    source = json.loads((EVIDENCE / "validation-r7-source-before.json").read_text(encoding="utf-8"))
    actual = {path: hashlib.sha256((ROOT / path).read_bytes()).hexdigest() for path in source}
    assert actual == source
    target = EVIDENCE / "current-standard-r7-receipt.json"
    jobs = (("ab", "drivetrain-ab.py", ["--output", str(EVIDENCE / "ab-mode-control-r7")]),
            ("grade", "grade-calibrated.py", [str(EVIDENCE / "grade-control-r7")]))
    receipt = {"status": "running", "scope": "current r7 native standard AB and grade only; not complete T2/visible/human gate",
               "source_before": source, "runner_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
               "jobs": [{"name": name, "script": script, "args": args, "status": "not_run",
                         "script_sha256": hashlib.sha256((EVIDENCE / script).read_bytes()).hexdigest()}
                        for name, script, args in jobs]}

    def save():
        target.write_text(json.dumps(receipt, indent=2) + "\n", encoding="utf-8")

    save()
    for row, (name, script, args) in zip(receipt["jobs"], jobs):
        row["status"] = "running"
        save()
        sys.argv = [script, *args]
        # 坡停脚本用SystemExit返回真实命令状态；只接受其成功退出。
        try:
            runpy.run_path(str(EVIDENCE / script), run_name="__main__")
        except SystemExit as result:
            if result.code not in (None, 0):
                raise
        folder = "ab-mode-control-r7" if name == "ab" else "grade-control-r7"
        report = json.loads((EVIDENCE / folder / "summary.json").read_text(encoding="utf-8"))
        assert report["status"] == "completed" and report["source_stable"]
        assert report["source_before"] == report["source_after"] == source
        if name == "ab":
            assert len(report["cases"]) == 22 and all("A" in case and "B" in case for case in report["cases"])
            row["completed_trials"] = 44
        else:
            assert len(report["trials"]) == 2 and report["passed"]
            row["completed_trials"] = 2
        row["status"] = "completed"
        save()
    after = {path: hashlib.sha256((ROOT / path).read_bytes()).hexdigest() for path in source}
    assert after == source
    receipt.update(status="completed_current_standard", source_after=after, source_stable=True)
    save()
    print("COMPLETE 44 standard AB trials and 2 grade trials", flush=True)


if __name__ == "__main__":
    main()
