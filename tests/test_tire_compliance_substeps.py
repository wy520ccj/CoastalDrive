"""子步工具的配置隔离、调度与失败账本；不替代真实矩阵证据。"""

import gzip
import json
import sys
from dataclasses import asdict
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
from physics import tire_compliance_substeps as probe


@pytest.mark.parametrize("mode", probe.MODES)
@pytest.mark.parametrize("case", probe.CASES)
def test_substep_pair_only_changes_substep_count(case, mode):
    a, b = (asdict(probe.substep_config(case, mode, steps)) for steps in probe.SUBSTEPS)
    assert a.pop("tire_substeps") == 2
    assert b.pop("tire_substeps") == 8
    assert a == b and a["tire_compliance"] is True


def test_synthetic_schedule_keeps_all_sixteen_trials_and_energy(tmp_path, monkeypatch):
    calls = []

    def synthetic_trial(case, enabled, duration, mode, vehicle_config):
        calls.append((mode, case, vehicle_config.tire_substeps, enabled, duration))
        summary = {key: float(vehicle_config.tire_substeps) for key in (
            "final_horizontal_speed_mps", "path_distance_m", "heading_change_deg",
            "peak_abs_yaw_rate_radps", "abs_yaw_error_integral_rad")}
        rows = [{"tick": tick, **{f"state.wheel_dynamics.{index}.force_residual": -.001
                                 for index in range(4)}} for tick in range(2)]
        return summary, rows

    monkeypatch.setattr(probe, "run_trial", synthetic_trial)
    monkeypatch.setattr(probe, "energy_summary", lambda rows: {"synthetic_row_count": len(rows)})
    output = tmp_path / "synthetic"
    report = probe.run(output)
    assert report["status"] == "completed" and report["source_unchanged"] is True
    assert len(calls) == 16
    assert calls == [(mode, case, steps, True, 6) for mode in probe.MODES
                     for case in probe.CASES for steps in probe.SUBSTEPS]
    for pair in report["trials"]:
        assert pair["eight_minus_two"]["path_distance_m"] == 6
        for steps in ("2", "8"):
            assert pair[steps]["energy"]["synthetic_row_count"] == 2
            assert pair[steps]["maximum_force_residual_n"] == .001
            with gzip.open(output / pair[steps]["csv_gz"], "rt", encoding="utf-8") as stream:
                assert len(stream.readlines()) == 3
    with pytest.raises(FileExistsError):
        probe.run(output)


def test_failed_trial_and_all_unrun_are_saved(tmp_path, monkeypatch):
    def failed_trial(*args, **kwargs):
        raise RuntimeError("synthetic failure")

    monkeypatch.setattr(probe, "run_trial", failed_trial)
    output = tmp_path / "failed"
    with pytest.raises(RuntimeError, match="synthetic failure"):
        probe.run(output)
    report = json.loads((output / "summary.json").read_text(encoding="utf-8"))
    assert report["status"] == "failed"
    assert report["failed_trial"] == ["game", "asphalt-brake", 2]
    assert len(report["not_run"]) == 15
    assert report["source_unchanged"] is True
    assert "tools/physics/tire_compliance_substeps.py" in report["source_before"]
