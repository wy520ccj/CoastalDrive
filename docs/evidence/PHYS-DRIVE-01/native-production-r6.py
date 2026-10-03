"""正式r6源码的原生轨迹，与冻结r5逐字节核对；不使用进程内原型。"""

import gzip
import hashlib
import json
from pathlib import Path
import runpy
import sys

EVIDENCE = Path(__file__).resolve().parent
ROOT = EVIDENCE.parents[2]


def main():
    source = json.loads((EVIDENCE / "matrix-reuse-r6-source-before.json").read_text(encoding="utf-8"))
    runner_hash = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    target = EVIDENCE / "native-production-r6-receipt.json"
    receipt = {"status": "running", "scope": "production r6, native trace equality only; not T2/visible/human gate",
               "runner_sha256": runner_hash, "source_before": source, "cases": []}
    target.write_text(json.dumps(receipt, indent=2) + "\n", encoding="utf-8")
    probe = runpy.run_path(str(ROOT / "tools/physics/drivetrain_probe.py"))
    for old_name, new_name, seconds, extra in (
        ("native-mode-control-r5", "native-mode-control-r6", 6., []),
        ("native-rigid-control-r5", "native-rigid-control-r6", 4., ["--rigid", "--cases", "reverse", "manual-shift"]),
    ):
        old, new = EVIDENCE / old_name, EVIDENCE / new_name
        sys.argv = ["drivetrain_probe.py", "--output", str(new), "--seconds", str(seconds), *extra]
        probe["main"]()
        expected = sorted(path.name for path in old.glob("*.jsonl.gz"))
        assert expected == sorted(path.name for path in new.glob("*.jsonl.gz"))
        for name in expected:
            with gzip.open(old / name, "rb") as stream:
                before = stream.read()
            with gzip.open(new / name, "rb") as stream:
                after = stream.read()
            receipt["cases"].append({"baseline": old_name, "candidate": new_name, "file": name,
                                     "ticks": before.count(b"\n"), "bytes_equal": before == after,
                                     "before_sha256": hashlib.sha256(before).hexdigest(),
                                     "after_sha256": hashlib.sha256(after).hexdigest()})
            target.write_text(json.dumps(receipt, indent=2) + "\n", encoding="utf-8")
            assert before == after, name
        summary = json.loads((new / "summary.json").read_text(encoding="utf-8"))
        assert summary["source_before"] == summary["source_after"] == source
    after = {path: hashlib.sha256((ROOT / path).read_bytes()).hexdigest() for path in source}
    assert after == source
    receipt.update(status="completed_identical_production_native", source_after=after,
                   source_stable=True, total_ticks=sum(case["ticks"] for case in receipt["cases"]))
    target.write_text(json.dumps(receipt, indent=2) + "\n", encoding="utf-8")
    print(f"IDENTICAL {len(receipt['cases'])} production traces / {receipt['total_ticks']} ticks", flush=True)


if __name__ == "__main__":
    main()
