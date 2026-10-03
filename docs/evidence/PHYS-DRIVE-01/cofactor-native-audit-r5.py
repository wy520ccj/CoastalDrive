"""独立进程内复用矩阵，逐字节对照已有16条原生轨迹；源码保持冻结。"""

import gzip
import hashlib
import json
from pathlib import Path
import runpy
import sys

EVIDENCE = Path(__file__).resolve().parent
ROOT = EVIDENCE.parents[2]
sys.path.insert(0, str(ROOT / "src"))

import tire_drivetrain


def main():
    experiment = EVIDENCE / "cofactor-reuse-audit-r5.py"
    functions = runpy.run_path(str(experiment))
    receipt = {"status": "running", "scope": "isolated process prototype, production source unchanged; not full T1 or performance gate",
               "algorithm_script_sha256": hashlib.sha256(experiment.read_bytes()).hexdigest(),
               "runner_script_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
               "cases": []}
    target = EVIDENCE / "cofactor-native-audit-r5.json"
    target.write_text(json.dumps(receipt, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    def plans(response, capacity, brake_capacity, efficiency):
        return functions["reused_plans"](response, capacity, brake_capacity, efficiency)[0]

    # 仅本进程中的函数绑定改变；后台完整T1与磁盘源文件均继续原实现。
    tire_drivetrain.clutch_brake_plans = plans
    probe = runpy.run_path(str(ROOT / "tools/physics/drivetrain_probe.py"))
    for baseline_name, candidate_name, seconds, extra in (
        ("native-mode-control-r5", "cofactor-native-flexible-r5", 6., []),
        ("native-rigid-control-r5", "cofactor-native-rigid-r5", 4., ["--rigid", "--cases", "reverse", "manual-shift"]),
    ):
        output = EVIDENCE / candidate_name
        sys.argv = ["drivetrain_probe.py", "--output", str(output), "--seconds", str(seconds), *extra]
        probe["main"]()
        baseline = EVIDENCE / baseline_name
        expected = sorted(path.name for path in baseline.glob("*.jsonl.gz"))
        actual = sorted(path.name for path in output.glob("*.jsonl.gz"))
        assert expected == actual, (expected, actual)
        for name in expected:
            with gzip.open(baseline / name, "rb") as stream:
                old = stream.read()
            with gzip.open(output / name, "rb") as stream:
                new = stream.read()
            case = {"baseline": baseline_name, "candidate": candidate_name, "file": name,
                    "ticks": old.count(b"\n"), "decompressed_bytes_equal": old == new,
                    "baseline_sha256": hashlib.sha256(old).hexdigest(),
                    "candidate_sha256": hashlib.sha256(new).hexdigest()}
            receipt["cases"].append(case)
            target.write_text(json.dumps(receipt, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            assert old == new, name
        native = json.loads((output / "summary.json").read_text(encoding="utf-8"))
        old_native = json.loads((baseline / "summary.json").read_text(encoding="utf-8"))
        assert native["source_before"] == native["source_after"] == old_native["source_before"]
    receipt["status"] = "completed_identical_native_traces"
    receipt["total_ticks"] = sum(case["ticks"] for case in receipt["cases"])
    target.write_text(json.dumps(receipt, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"IDENTICAL {len(receipt['cases'])} traces / {receipt['total_ticks']} ticks", flush=True)


if __name__ == "__main__":
    main()
