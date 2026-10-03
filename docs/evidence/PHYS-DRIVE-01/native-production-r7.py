"""正式r7原生轨迹；完整保留与r6的差异，不把控制修复冒充逐字节不变。"""

import gzip
import hashlib
import json
from pathlib import Path
import runpy
import sys

EVIDENCE = Path(__file__).resolve().parent
ROOT = EVIDENCE.parents[2]


def flatten(value, prefix=""):
    if isinstance(value, dict):
        return {key: leaf for name, child in value.items()
                for key, leaf in flatten(child, f"{prefix}.{name}" if prefix else name).items()}
    if isinstance(value, list):
        return {key: leaf for index, child in enumerate(value)
                for key, leaf in flatten(child, f"{prefix}.{index}").items()}
    return {prefix: value}


def main():
    source = json.loads((EVIDENCE / "validation-r7-source-before.json").read_text(encoding="utf-8"))
    target = EVIDENCE / "native-production-r7-receipt.json"
    receipt = {"status": "running", "scope": "production r7 native cases and complete field differences; not T2/visible/human gate",
               "runner_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
               "source_before": source, "cases": []}
    target.write_text(json.dumps(receipt, indent=2) + "\n", encoding="utf-8")
    probe = runpy.run_path(str(ROOT / "tools/physics/drivetrain_probe.py"))
    for old_name, new_name, seconds, extra in (
        ("native-mode-control-r6", "native-mode-control-r7", 6., []),
        ("native-rigid-control-r6", "native-rigid-control-r7", 4., ["--rigid", "--cases", "reverse", "manual-shift"]),
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
            first, second = before.splitlines(), after.splitlines()
            assert len(first) == len(second)
            differences = {}
            for tick, (left, right) in enumerate(zip(first, second)):
                a, b = flatten(json.loads(left)), flatten(json.loads(right))
                assert a.keys() == b.keys()
                for field in a:
                    if a[field] != b[field]:
                        if field not in differences:
                            differences[field] = {"count": 0, "first_tick": tick,
                                                  "first_before": a[field], "first_after": b[field]}
                        differences[field]["count"] += 1
            receipt["cases"].append({"baseline": old_name, "candidate": new_name, "file": name,
                                     "ticks": len(first), "bytes_equal": before == after,
                                     "before_sha256": hashlib.sha256(before).hexdigest(),
                                     "after_sha256": hashlib.sha256(after).hexdigest(),
                                     "differing_fields": differences})
            target.write_text(json.dumps(receipt, indent=2) + "\n", encoding="utf-8")
        summary = json.loads((new / "summary.json").read_text(encoding="utf-8"))
        assert summary["source_before"] == summary["source_after"] == source
    after = {path: hashlib.sha256((ROOT / path).read_bytes()).hexdigest() for path in source}
    assert after == source
    receipt.update(status="completed_production_native", source_after=after,
                   source_stable=True, total_ticks=sum(case["ticks"] for case in receipt["cases"]))
    target.write_text(json.dumps(receipt, indent=2) + "\n", encoding="utf-8")
    print(f"COMPLETE {len(receipt['cases'])} production traces / {receipt['total_ticks']} ticks", flush=True)


if __name__ == "__main__":
    main()
