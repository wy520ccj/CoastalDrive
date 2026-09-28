"""以全新进程测量可见主菜单和进入八车自由驾驶的启动时间。"""

import argparse
import json
import os
import statistics
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--runs", type=int, default=3)
    parser.add_argument("--executable", type=Path, help="可选：测量当前构建的独立版可执行文件")
    args = parser.parse_args()
    if args.runs < 1:
        parser.error("--runs must be positive")
    output = args.output.resolve()
    executable = args.executable.resolve() if args.executable else None
    if executable is not None and not executable.is_file():
        parser.error(f"executable does not exist: {executable}")
    output.mkdir(parents=True, exist_ok=False)
    reports = []
    for index in range(args.runs):
        run_dir = output / f"run-{index + 1:02d}"
        run_dir.mkdir()
        user_data = run_dir / "user-data"
        user_data.mkdir()
        report_path = run_dir / "startup.json"
        env = os.environ.copy()
        env["LOCALAPPDATA"] = str(user_data)
        started = time.perf_counter_ns()
        env["COASTALDRIVE_STARTUP_ORIGIN_NS"] = str(started)
        command = ([str(executable)] if executable else [sys.executable, str(ROOT / "src/main.py")])
        result = subprocess.run(
            [*command, "--profile-startup", str(report_path)],
            cwd=ROOT, env=env, capture_output=True, text=True, timeout=120, check=False,
        )
        if result.returncode != 0 or not report_path.is_file():
            (run_dir / "stdout.txt").write_text(result.stdout, encoding="utf-8")
            (run_dir / "stderr.txt").write_text(result.stderr, encoding="utf-8")
            raise RuntimeError(f"第 {index + 1} 次启动失败；查看 {run_dir / 'stderr.txt'}")
        report = json.loads(report_path.read_text(encoding="utf-8"))
        reports.append(report)
        print(
            f"run {index + 1}: first frame {report['time_to_first_frame_s']:.3f}s, "
            f"menu {report['time_to_menu_usable_s']:.3f}s, "
            f"8-car transition {report['drive_transition_s']:.3f}s"
        )
    summary = {
        "runs": args.runs,
        "method": "fresh process per run; OS file cache and GPU shader cache not cleared",
        "target": str(executable) if executable else "source Python entry point",
        "scenario": reports[0]["scenario"],
        "resolution": reports[0]["resolution"],
        "renderer": reports[0]["renderer"],
        "first_frame_median_s": statistics.median(r["time_to_first_frame_s"] for r in reports),
        "menu_usable_median_s": statistics.median(r["time_to_menu_usable_s"] for r in reports),
        "drive_transition_median_s": statistics.median(r["drive_transition_s"] for r in reports),
        "individual_reports": [f"run-{i + 1:02d}/startup.json" for i in range(args.runs)],
    }
    (output / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print("Cold startup: fresh process (OS cache not cleared)")
    for label, event in (
        ("Python entry", "entrypoint_ready"),
        ("Panda3D / window", "window_initialized"),
        ("Renderer / simplepbr", "renderer_initialized"),
        ("Primary font", "primary_font_loaded"),
        ("Display font / UI assets", "display_font_loaded"),
        ("UI completion", "ui_ready"),
    ):
        duration = statistics.median(
            next(item["since_previous_s"] for item in report["timeline"]
                 if item["event"] == event)
            for report in reports
        )
        print(f"  {label:<27} {duration:>7.3f} s")
    print("  Gameplay Scene at menu:      none")
    print(f"  {'First rendered frame':<27} {summary['first_frame_median_s']:>7.3f} s from process")
    print(f"  {'Main menu usable':<27} {summary['menu_usable_median_s']:>7.3f} s from process")
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
