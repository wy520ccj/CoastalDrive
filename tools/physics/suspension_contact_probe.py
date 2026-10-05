"""原单侧翻覆工况短对照；独立检查每个接点是否位于真实Box面。"""

import argparse
import gzip
import hashlib
import json
import math
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT / "src"), str(ROOT / "tools")]

from panda3d.bullet import BulletBoxShape
from panda3d.core import Vec3
from physics.suspension_coupled_probe import trial


def box_surface_error(point):
    """工况的真实Box外廓：中心(-.84,0,-.05)，半边长(.4,40,.05)。"""
    local = (point[0] + .84, point[1], point[2] + .05)
    distances = tuple(abs(x) - half for x, half in zip(local, (.4, 40., .05)))
    return max(max(distances), 0.) + min(abs(value) for value in distances)


def rounded_box_surface_error(point):
    """凸体扫掠使用原生Box内核与margin；独立SDF检查棱角和面。"""
    shape = BulletBoxShape(Vec3(.4, 40., .05))
    half, margin = shape.getHalfExtentsWithoutMargin(), shape.getMargin()
    center = tuple(Vec3(-.84, 0., -.05))
    local = tuple(point[a] - center[a] for a in range(3))
    delta = tuple(abs(local[a]) - half[a] for a in range(3))
    distance = math.sqrt(sum(max(d, 0.) ** 2 for d in delta)) + min(max(delta), 0.)
    return abs(distance - margin)


def run(output, prior):
    output.mkdir(parents=True, exist_ok=False)
    hashes = lambda: {p.relative_to(ROOT).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
                     for group in ("src", "tests", "tools") for p in sorted((ROOT / group).rglob("*.py"))}
    report = {"status": "running", "source_before": hashes(), "baseline": prior.relative_to(ROOT).as_posix(),
              "baseline_source_sha256": json.loads((prior / "summary.json").read_text(encoding="utf-8"))["source_after"],
              "protocol": "unchanged one-side fixture/initial conditions/commands; 360 native 120Hz steps per mode; finite-radius sphere envelope, native core+margin Box SDF independently checked; saved prior trace reused", "results": []}
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
            error = max(rounded_box_surface_error(c["contact_point"]) for row in rows
                        for c in row["car"]["wheel_contacts"] if c["in_contact"])
            assert error < 1e-6
            old_trace = prior / f"{mode}-one-side.jsonl.gz"
            with gzip.open(old_trace, "rt", encoding="utf-8") as stream:
                old_rows = [json.loads(line) for line in stream]
            old_error = max(box_surface_error(c["contact_point"]) for row in old_rows
                            for c in row["car"]["wheel_contacts"] if c["in_contact"])
            report["results"].append({**result, "trace": name, "max_box_surface_error_m": error,
                                      "baseline_trace": old_trace.relative_to(ROOT).as_posix(),
                                      "baseline_trace_sha256": hashlib.sha256(old_trace.read_bytes()).hexdigest(),
                                      "baseline_max_nominal_box_surface_error_m": old_error,
                                      "baseline_sum_signed_contact_offset_work_j": sum(row["car"]["suspension_state"]["step"]["contact_offset_work"] for row in old_rows),
                                      "side_contact_ticks": [row["tick"] for row in rows if any(c["in_contact"] and c["contact_normal"][2] < .5 for c in row["car"]["wheel_contacts"])]})
            pending.remove(mode)
            print(f"DONE {mode}: current core+margin surface error {error:.6g}m; offset {result['sum_signed_contact_offset_work_j']:.6g}J", flush=True)
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
    parser.add_argument("--prior", type=Path, default=ROOT / "docs/evidence/PHYS-SUSP-01/contact-native-r1")
    args = parser.parse_args()
    run(args.output, args.prior.resolve())
