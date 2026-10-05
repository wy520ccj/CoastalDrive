"""原单侧翻覆工况短对照；独立检查每个接点是否位于真实Box面。"""

import argparse
import gzip
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT / "src"), str(ROOT / "tools")]

from physics.suspension_coupled_probe import trial


def box_surface_error(point):
    """工况的真实Box外廓：中心(-.84,0,-.05)，半边长(.4,40,.05)。"""
    local = (point[0] + .84, point[1], point[2] + .05)
    distances = tuple(abs(x) - half for x, half in zip(local, (.4, 40., .05)))
    return max(max(distances), 0.) + min(abs(value) for value in distances)


def run(output):
    output.mkdir(parents=True, exist_ok=False)
    hashes = lambda: {p.relative_to(ROOT).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
                     for group in ("src", "tests", "tools") for p in sorted((ROOT / group).rglob("*.py"))}
    report = {"status": "running", "source_before": hashes(), "baseline": "f7c971f",
              "protocol": "unchanged one-side fixture/initial conditions/commands; 360 native 120Hz steps per mode; true Box faces checked independently", "results": []}
    pending = ["game", "simulation"]
    try:
        for mode in pending[:]:
            rows = []
            name = f"{mode}-one-side.jsonl.gz"
            try:
                result = trial(mode, True, "one-side", rows)
            finally:
                with gzip.open(output / name, "wt", encoding="utf-8") as stream:
                    for row in rows:
                        stream.write(json.dumps(row, ensure_ascii=False, allow_nan=False) + "\n")
            error = max(box_surface_error(c["contact_point"]) for row in rows
                        for c in row["car"]["wheel_contacts"] if c["in_contact"])
            assert error < 1e-6
            prior = ROOT / "docs/evidence/PHYS-SUSP-01/passive-native-r2" / f"{mode}-one-side-coupled.jsonl.gz"
            with gzip.open(prior, "rt", encoding="utf-8") as stream:
                old_rows = [json.loads(line) for line in stream]
            old_error = max(box_surface_error(c["contact_point"]) for row in old_rows
                            for c in row["car"]["wheel_contacts"] if c["in_contact"])
            report["results"].append({**result, "trace": name, "max_box_surface_error_m": error,
                                      "baseline_trace": prior.relative_to(ROOT).as_posix(),
                                      "baseline_trace_sha256": hashlib.sha256(prior.read_bytes()).hexdigest(),
                                      "baseline_max_box_surface_error_m": old_error})
            pending.remove(mode)
            print(f"DONE {mode}: surface error {old_error:.6g} -> {error:.6g}m; offset {result['sum_signed_contact_offset_work_j']:.6g}J", flush=True)
    except (ArithmeticError, AssertionError, ValueError, OSError) as error:
        report.update(status="failed", error=repr(error), failed_mode=pending[0], not_run=pending[1:])
        raise
    else:
        report["status"] = "completed"
    finally:
        report["source_after"] = hashes()
        report["source_stable"] = report["source_before"] == report["source_after"]
        (output / "summary.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    assert report["source_stable"]


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    run(parser.parse_args().output)
