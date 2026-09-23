"""验证工具不会误报成功、覆盖旧证据或意外启动重检查。"""

import json
import os
import sys

import pytest
from validate import Check, execute_plan, main, make_plan, run_check


def test_small_tiers_require_scope_and_cannot_silently_run_the_full_suite(tmp_path):
    for tier in ("T0", "T1"):
        with pytest.raises(ValueError, match="require"):
            make_plan(tier, [], [], tmp_path)
    for tier in ("T2", "T3"):
        with pytest.raises(ValueError, match="full suite"):
            make_plan(tier, ["traffic"], [], tmp_path)
    plan = make_plan("T0", ["traffic"], [], tmp_path)
    assert [check.name for check in plan] == ["ruff", "pytest"]
    assert "tests/test_traffic_recovery.py" in plan[1].args
    assert "tests/test_appearance.py" not in plan[1].args
    assert "tests/test_audio_settings.py" in make_plan("T0", ["audio"], [], tmp_path)[1].args
    plan = make_plan("T1", ["traffic"], [], tmp_path)
    drives = [check for check in plan if check.name.startswith("hills-")]
    assert len(drives) == 2
    assert all(check.args[check.args.index("--seconds") + 1] == "30" for check in drives)
    assert not any("--distance" in check.args for check in plan)


def test_t3_has_long_runs_without_claiming_a_human_gate(tmp_path):
    plan = make_plan("T3", [], [], tmp_path)
    assert len([check for check in plan if check.name.startswith("long-hills-")]) == 10
    assert plan[-1].name == "hills-100km" and "100000" in plan[-1].args
    assert not any("--window-smoke" in check.args for check in plan)


@pytest.mark.parametrize("payload", ['{"passed":false}', '{}', '[]', 'broken', None])
def test_zero_exit_does_not_hide_false_missing_or_malformed_evidence(tmp_path, payload):
    report = tmp_path / "report.json"
    if payload is not None:
        report.write_text(payload, encoding="utf-8")
    result = run_check(Check("probe", ["-c", "pass"], (report,)),
                       tmp_path / "probe.log", 10, os.environ.copy())
    assert result["returncode"] == 0
    assert result["status"] == "failed"
    assert result["error"]


def test_process_failure_wins_over_a_positive_report(tmp_path):
    report = tmp_path / "report.json"
    report.write_text('{"passed":true}', encoding="utf-8")
    result = run_check(Check("probe", ["-c", "raise SystemExit(3)"], (report,)),
                       tmp_path / "probe.log", 10, os.environ.copy())
    assert result["status"] == "failed" and result["returncode"] == 3


def test_timeout_cannot_pass(tmp_path):
    result = run_check(Check("probe", ["-c", "import time; time.sleep(30)"]),
                       tmp_path / "probe.log", 0.1, os.environ.copy())
    assert result["status"] == "timeout"


def test_failure_stops_following_commands_and_preserves_summary(tmp_path):
    output = tmp_path / "run"
    checks = [Check("bad", ["-c", "print('failure detail'); raise SystemExit(2)"]),
              Check("later", ["-c", "raise RuntimeError('must not execute')"])]
    assert execute_plan(checks, output, "T1", 10, {"git_head": "test"}) == 1
    summary = json.loads((output / "summary.json").read_text(encoding="utf-8"))
    assert summary["passed"] is False
    assert [row["status"] for row in summary["checks"]] == ["failed", "not_run"]
    assert "failure detail" in (output / "bad.log").read_text(encoding="utf-8")
    with pytest.raises(FileExistsError):
        execute_plan(checks, output, "T1", 10, {})


def test_success_is_scoped_to_automatic_checks_and_uses_isolated_settings(tmp_path):
    output = tmp_path / "run"
    report = output / "probe.json"
    code = (
        "import json, os; from pathlib import Path; "
        f"Path({str(report)!r}).write_text(json.dumps({{'passed': True, "
        "'localappdata': os.environ['LOCALAPPDATA']}))"
    )
    assert execute_plan([Check("probe", ["-c", code], (report,))],
                        output, "T3", 10, {}) == 0
    summary = json.loads((output / "summary.json").read_text(encoding="utf-8"))
    assert summary["passed"] is True
    assert summary["human_gate"] == "pending"
    assert summary["stage_gate"] == "not_assessed"
    assert json.loads(report.read_text())["localappdata"] == str(output / "user-data")


def test_interruption_is_recorded_and_does_not_continue(tmp_path, monkeypatch):
    def interrupt(*args, **kwargs):
        raise KeyboardInterrupt

    monkeypatch.setattr("validate.subprocess.run", interrupt)
    output = tmp_path / "run"
    assert execute_plan([Check("probe", ["-c", "pass"])], output, "T1", 10, {}) == 130
    summary = json.loads((output / "summary.json").read_text(encoding="utf-8"))
    assert summary["status"] == "interrupted" and summary["passed"] is False


def test_dry_run_from_another_directory_creates_no_evidence(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    output = tmp_path / "preview"
    assert main(["T3", "--dry-run", "--output", str(output)]) == 0
    assert not output.exists()
    assert sys.executable in capsys.readouterr().out
