"""对比固定输入快照；四元数q与-q表示相同旋转，其余物理字段必须完全一致。"""

import argparse
import json
from pathlib import Path


def compare(before, after):
    results = []
    assert len(before) == len(after)
    for old, new in zip(before, after, strict=True):
        assert old["shape"] == new["shape"] and old["ticks"] == new["ticks"]
        failures, deltas, sign_flips = [], [], []

        def visit(a, b, path, failures=failures, deltas=deltas, sign_flips=sign_flips):
            if isinstance(a, dict):
                assert a.keys() == b.keys()
                for key in a:
                    visit(a[key], b[key], path + "." + key)
            elif isinstance(a, list):
                assert len(a) == len(b)
                if ".wheels[" in path and path.endswith(".orientation"):
                    sign = 1 if sum(x*y for x, y in zip(a, b, strict=True)) >= 0 else -1
                    delta = max(abs(x-sign*y) for x, y in zip(a, b, strict=True))
                    deltas.append(delta)
                    sign_flips.append(sign < 0)
                    if delta > 1e-6:
                        failures.append(path)
                else:
                    for i, (x, y) in enumerate(zip(a, b, strict=True)):
                        visit(x, y, path + f"[{i}]")
            elif a != b:
                failures.append(path)

        visit(old["snapshots"], new["snapshots"], "snapshot")
        results.append({"shape": old["shape"], "passed": not failures,
                        "quaternions": len(deltas), "sign_flips": sum(sign_flips),
                        "max_aligned_quaternion_delta": max(deltas, default=0),
                        "unequal_fields": failures})
    return {"passed": all(row["passed"] for row in results), "routes": results}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--before", type=Path, required=True)
    parser.add_argument("--after", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = compare(json.loads(args.before.read_text(encoding="utf-8")),
                     json.loads(args.after.read_text(encoding="utf-8")))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(json.dumps(result))
    if not result["passed"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
