"""按级别串行验证；终端显示简短结论，详细输出保存在每次独立的日志中。"""

import argparse
import json
import os
import subprocess
import sys
import time
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
AREAS = {
    "workflow": ["test_validation_runner"],
    "core": ["test_core", "test_stage4"],
    "vehicle": ["test_h1_vehicle", "test_driving_response", "test_curved_driving"],
    "traffic": ["test_h4a_traffic", "test_traffic_behavior", "test_traffic_impacts",
                "test_traffic_recovery"],
    "road": ["test_endless", "test_highway_segments", "test_highway_curve",
             "test_highway_surface", "test_curve_mesh", "test_curved_boundaries"],
    "gameplay": ["test_race", "test_highway_run", "test_stage4", "test_h3_review"],
    "appearance": ["test_appearance"],
}


@dataclass
class Check:
    name: str
    args: list[str]
    reports: tuple[Path, ...] = ()


def make_plan(tier, areas, tests, output):
    targets = list(dict.fromkeys(
        [f"tests/{name}.py" for area in areas for name in AREAS[area]] + tests
    ))
    if tier in ("T0", "T1") and not targets:
        raise ValueError("T0/T1 require --area or --tests; no implicit full suite")
    if tier in ("T2", "T3") and (areas or tests):
        raise ValueError("T2/T3 always use the full suite; omit --area and --tests")
    checks = [Check("ruff", ["-m", "ruff", "check", "src", "tests", "tools"]),
              Check("pytest", ["-m", "pytest", "-q", *(targets or ["tests"])])]
    if tier == "T0" or (tier == "T1" and areas == ["workflow"] and not tests):
        return checks
    for seed in (0, 17, 23):
        checks.append(Check(f"headless-{seed}", [
            "src/main.py", "--headless", "--track", "test", "--steps", "1200",
            "--seed", str(seed),
        ]))
    if tier == "T1":
        if set(areas) & {"traffic", "road"}:
            for seed in (0, 23):
                path = output / f"hills-{seed}.json"
                checks.append(Check(f"hills-{seed}", [
                    "tools/curve_drive_check.py", "--shape", "hills", "--seconds", "30",
                    "--seed", str(seed), "--output", str(path),
                ], (path,)))
        return checks

    handling = output / "handling"
    checks.append(Check("handling", ["tools/h1_benchmark.py", "--output", str(handling)],
                        (handling / "handling.json",)))
    for name, script in (("surface", "curve_surface_check"),
                         ("interactions", "traffic_interaction_check")):
        path = output / f"{name}.json"
        checks.append(Check(name, [f"tools/{script}.py", "--output", str(path)], (path,)))
    for track in ("coastal", "highway"):
        path = output / f"finite-{track}.json"
        checks.append(Check(f"finite-{track}", [
            "tools/h4a_traffic_check.py", "--track", track, "--seconds", "30",
            "--seed", "23", "--output", str(path),
        ], (path,)))
    for seed in (0, 17, 23):
        folder = output / f"straight-{seed}"
        checks.append(Check(f"straight-{seed}", [
            "tools/endless_check.py", "--seconds", "120", "--seed", str(seed),
            "--output", str(folder),
        ], (folder / f"seed-{seed}.json",)))
        path = output / f"hills-{seed}.json"
        checks.append(Check(f"hills-{seed}", [
            "tools/curve_drive_check.py", "--shape", "hills", "--seconds", "120",
            "--seed", str(seed), "--output", str(path),
        ], (path,)))
    if tier == "T3":
        for seed in range(10):
            path = output / f"long-hills-{seed}.json"
            checks.append(Check(f"long-hills-{seed}", [
                "tools/curve_drive_check.py", "--shape", "hills", "--seconds", "600",
                "--seed", str(seed), "--output", str(path),
            ], (path,)))
        path = output / "hills-100km.json"
        checks.append(Check("hills-100km", [
            "tools/curve_drive_check.py", "--shape", "hills", "--distance", "100000",
            "--traffic-count", "0", "--seed", "17", "--output", str(path),
        ], (path,)))
    return checks


def run_check(check, logfile, timeout, env):
    started = time.monotonic()
    result = {"status": "failed", "returncode": None, "error": None}
    try:
        with logfile.open("w", encoding="utf-8") as stream:
            process = subprocess.run(
                [sys.executable, *check.args], cwd=ROOT, env=env,
                stdout=stream, stderr=subprocess.STDOUT, timeout=timeout, check=False,
            )
        result["returncode"] = process.returncode
        if process.returncode != 0:
            result["error"] = f"process exited {process.returncode}"
        else:
            for path in check.reports:
                report = json.loads(path.read_text(encoding="utf-8"))
                if not isinstance(report, dict) or report.get("passed") is not True:
                    raise ValueError(f"report does not say passed=true: {path}")
            result["status"] = "passed"
    except subprocess.TimeoutExpired:
        result.update(status="timeout", error=f"exceeded {timeout} wall seconds")
    except KeyboardInterrupt:
        result.update(status="interrupted", error="interrupted by user")
    except (OSError, ValueError) as error:
        result["error"] = str(error)
    result["seconds"] = round(time.monotonic() - started, 3)
    return result


def git_value(*args):
    result = subprocess.run(["git", *args], cwd=ROOT, capture_output=True,
                            text=True, encoding="utf-8", errors="replace", check=True)
    return result.stdout.strip()


def execute_plan(checks, output, tier, timeout, metadata):
    # 每次使用新目录，避免上次的成功文件掩盖本次失败。
    output.mkdir(parents=True, exist_ok=False)
    env = {**os.environ, "PYTHONUTF8": "1", "PYTHONIOENCODING": "utf-8",
           "LOCALAPPDATA": str(output / "user-data")}
    summary = {
        **metadata, "tier": tier, "status": "running", "passed": False,
        "stage_gate": "not_assessed", "human_gate": "pending",
        "checks": [{"name": check.name, "command": [sys.executable, *check.args],
                    "reports": [str(path) for path in check.reports],
                    "log": str(output / f"{check.name}.log"), "status": "not_run"}
                   for check in checks],
    }
    summary_path = output / "summary.json"

    def save():
        summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n",
                                encoding="utf-8")

    save()
    for check, row in zip(checks, summary["checks"], strict=True):
        row["status"] = "running"
        save()
        print(f"RUN {check.name}", flush=True)
        row.update(run_check(check, Path(row["log"]), timeout, env))
        save()
        print(f"{row['status'].upper()} {check.name} ({row['seconds']:.1f}s)", flush=True)
        if row["status"] != "passed":
            summary["status"] = row["status"]
            print(f"  {row['error']}\n  Log: {row['log']}", flush=True)
            break
    else:
        summary.update(status="passed", passed=True)
    save()
    print(f"Summary: {summary_path}", flush=True)
    if tier == "T3":
        print("Automatic checks only. Visible-window, performance and human gates remain pending.")
    return 0 if summary["passed"] else 130 if summary["status"] == "interrupted" else 1


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("tier", choices=("T0", "T1", "T2", "T3"))
    parser.add_argument("--area", choices=tuple(AREAS), action="append", default=[])
    parser.add_argument("--tests", nargs="+", default=[], help="pytest paths or node IDs")
    parser.add_argument("--dry-run", action="store_true", help="list commands without running")
    parser.add_argument("--output", type=Path, help="new directory; relative to repository root")
    parser.add_argument("--timeout", type=float, default=1800, help="wall seconds per check")
    args = parser.parse_args(argv)
    if not 0 < args.timeout < float("inf"):
        parser.error("--timeout must be positive and finite")
    output = args.output or Path("logs/validation") / (
        datetime.now(UTC).strftime("%Y%m%d-%H%M%S-%fZ") + f"-{args.tier}"
    )
    output = (ROOT / output).resolve()
    try:
        checks = make_plan(args.tier, args.area, args.tests, output)
    except ValueError as error:
        parser.error(str(error))
    if args.dry_run:
        for check in checks:
            print(subprocess.list2cmdline([sys.executable, *check.args]))
        print("Stage/human gates are separate; see docs/tasks/README.md.")
        return 0
    if output.exists():
        parser.error(f"refusing to overwrite existing run: {output}")
    metadata = {"started_utc": datetime.now(UTC).isoformat(),
                "git_head": git_value("rev-parse", "HEAD"),
                "git_status": git_value("status", "--short"),
                "python": sys.version, "areas": args.area, "tests": args.tests}
    return execute_plan(checks, output, args.tier, args.timeout, metadata)


if __name__ == "__main__":
    raise SystemExit(main())
