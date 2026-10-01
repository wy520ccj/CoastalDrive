"""柔性布尔隔离、力阶段能量累计与真实短试验导出。"""

import csv
import gzip
import json
import sys
from dataclasses import asdict
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
from physics.esc_probe import MODES
from physics.tire_compliance_probe import (
    DISSIPATION_FIELDS,
    LOAD_CASES,
    run_matrix,
    run_trial,
    source_hashes,
    trial_config,
)


@pytest.mark.parametrize("mode", MODES)
@pytest.mark.parametrize("case", LOAD_CASES)
def test_pair_only_changes_compliance_bool(case, mode):
    a, b = (asdict(trial_config(case, candidate, mode)) for candidate in (False, True))
    assert a.pop("tire_compliance") is False
    assert b.pop("tire_compliance") is True
    assert a == b
    assert (a["tire_peak_load_exponent"], a["longitudinal_load_exponent"],
            a["lateral_load_exponent"]) == (.90, .90, .85)
    assert a["tire_contact_stiffness"] == 150000
    assert a["tire_contact_damping"] == 1000
    assert all(a[section][switch] for section, switch in
               (("braking", "abs_enabled"), ("traction", "tcs_enabled"), ("stability", "esc_enabled")))


@pytest.mark.parametrize("case", ("acceleration", "constant-turn"))
def test_real_short_trial_energy_and_control_account(case):
    trials = [run_trial(case, candidate, .1) for candidate in (False, True)]
    assert all(summary["ticks"] == 12 for summary, _rows in trials)
    for old, new in zip(trials[0][1], trials[1][1]):
        assert {key: value for key, value in old.items() if key.startswith("command.")} == {
            key: value for key, value in new.items() if key.startswith("command.")}
    for summary, rows in trials:
        for index, wheel in enumerate(summary["energy"]["wheels"]):
            prefix = f"state.wheel_dynamics.{index}."
            for field in DISSIPATION_FIELDS:
                assert wheel[f"{field}_sum_j"] == pytest.approx(sum(row[prefix+field] for row in rows[1:]))
            assert wheel["peak_elastic_energy_j"] == max(row[prefix+"elastic_energy"] for row in rows)
            for row in rows[1:]:
                assert prefix+"force_patch_kappa" in row
                assert prefix+"force_patch_alpha" in row
                assert row[prefix+"force_contact_tick"] < row[prefix+"sample_tick"]
    assert max(wheel["peak_deformation_m"] for wheel in trials[0][0]["energy"]["wheels"]) == 0
    assert max(wheel["peak_elastic_energy_j"] for wheel in trials[1][0]["energy"]["wheels"]) > 0


def test_compressed_raw_rows_and_mode_energy_preserved(tmp_path):
    output = tmp_path / "compliance"
    report = run_matrix(output, .05, ("acceleration",), ("simulation",))
    assert report["status"] == "completed"
    assert report["source_sha256_before"] == report["source_sha256_after"]
    for label in ("A", "B"):
        with gzip.open(output / f"simulation-acceleration-{label}.csv.gz", "rt", newline="", encoding="utf-8") as stream:
            rows = list(csv.DictReader(stream))
        assert [int(row["tick"]) for row in rows] == list(range(7))
        assert rows[-1]["state.wheel_dynamics.0.elastic_energy"]
        for index in range(4):
            assert report["mode_energy"]["simulation"][label]["wheels"][index]["material_dissipation_sum_j"] == (
                report["cases"][0][label]["energy"]["wheels"][index]["material_dissipation_sum_j"])
    with pytest.raises(FileExistsError):
        run_matrix(output, .05)


def test_failure_and_unrun_trials_recorded(tmp_path):
    output = tmp_path / "failed"
    with pytest.raises(ValueError):
        run_matrix(output, 0, ("acceleration", "constant-turn"), ("game",))
    report = json.loads((output / "summary.json").read_text(encoding="utf-8"))
    assert report["status"] == "failed"
    assert report["failed_trial"] == ["game", "acceleration", "A"]
    assert report["not_run"] == [["game", "acceleration", "B"],
                                  ["game", "constant-turn", "A"], ["game", "constant-turn", "B"]]
    hashes = source_hashes()
    assert all(path in hashes for path in ("src/tire_compliance.py", "src/wheel_dynamics.py",
        "tools/physics/esc_probe.py", "tools/physics/tire_compliance_probe.py", "tools/physics/tire_load_probe.py"))
