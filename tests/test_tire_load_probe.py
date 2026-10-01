"""载荷A/B只改指数，并完整保留实步轮荷/刚度/峰值证据。"""

import csv
import gzip
import json
import sys
from dataclasses import asdict
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
from physics.esc_probe import CASES, FIXED_DT, MODES, command_at, initial_speed, run_trial
from physics.tire_load_probe import (
    EXPONENT_FIELDS,
    LOAD_CASES,
    run_matrix,
    source_hashes,
    trial_config,
)


@pytest.mark.parametrize("mode", MODES)
@pytest.mark.parametrize("case", LOAD_CASES)
def test_pair_changes_only_three_load_exponents(mode, case):
    a, b = (asdict(trial_config(case, candidate, mode)) for candidate in (False, True))
    assert [a.pop(key) for key in EXPONENT_FIELDS] == [1, 1, 1]
    assert [b.pop(key) for key in EXPONENT_FIELDS] == [.90, .90, .85]
    assert a == b
    assert all(a[section][switch] for section, switch in
               (("braking", "abs_enabled"), ("traction", "tcs_enabled"), ("stability", "esc_enabled")))


def test_load_cases_extend_without_changing_esc_matrix():
    assert len(CASES) == 9 and len(LOAD_CASES) == 11
    assert initial_speed("acceleration") == 0
    assert initial_speed("constant-turn") == pytest.approx(40/3.6)
    for time_s in (0, .5, 2, 6):
        assert command_at("acceleration", time_s)[1].throttle == 1
        circle = command_at("constant-turn", time_s)[1]
        assert circle.steering == 3 and circle.throttle == .15 and circle.brake == 0


@pytest.mark.parametrize("case", ("acceleration", "constant-turn"))
def test_real_pair_retains_same_inputs_and_actual_load_feedback(case):
    trials = [run_trial(case, True, .1, vehicle_config=trial_config(case, candidate))
              for candidate in (False, True)]
    a, b = trials[0][1], trials[1][1]
    assert len(a) == len(b) == 13
    for old, new in zip(a, b):
        assert {key: value for key, value in old.items() if key.startswith("command.")} == {
            key: value for key, value in new.items() if key.startswith("command.")}
    for rows in (a, b):
        for row in rows[1:]:
            for index in range(4):
                for field in ("normal_load", "force_grip", "force_longitudinal_stiffness", "force_lateral_stiffness"):
                    key = f"state.wheel_dynamics.{index}.{field}"
                    assert key in row
                    assert row[key] > 0


def test_matrix_compresses_every_tick_and_refuses_overwrite(tmp_path):
    output = tmp_path / "load"
    report = run_matrix(output, .1, ("acceleration",), ("simulation",))
    assert report["status"] == "completed"
    assert report["source_sha256_before"] == report["source_sha256_after"]
    for label in ("A", "B"):
        with gzip.open(output / f"simulation-acceleration-{label}.csv.gz", "rt", newline="", encoding="utf-8") as stream:
            rows = list(csv.DictReader(stream))
        assert [int(row["tick"]) for row in rows] == list(range(13))
        assert rows[-1]["state.wheel_dynamics.0.force_grip"]
    with pytest.raises(FileExistsError):
        run_matrix(output, FIXED_DT)


def test_failure_and_not_run_account_preserved(tmp_path):
    output = tmp_path / "failed"
    with pytest.raises(ValueError):
        run_matrix(output, 0, ("acceleration", "constant-turn"), ("game",))
    report = json.loads((output / "summary.json").read_text(encoding="utf-8"))
    assert report["failed_trial"] == ["game", "acceleration", "A"]
    assert report["not_run"] == [["game", "acceleration", "B"],
                                  ["game", "constant-turn", "A"], ["game", "constant-turn", "B"]]
    hashes = source_hashes()
    assert all(path in hashes for path in ("src/tire_forces.py", "src/vehicle_stability.py",
                                          "tools/physics/esc_probe.py", "tools/physics/tire_load_probe.py"))


def test_explicit_override_rejects_esc_label_conflict():
    with pytest.raises(ValueError, match="ESC"):
        run_trial("acceleration", False, .1, vehicle_config=trial_config("acceleration", True))


def test_acceleration_initial_rest_is_not_a_braking_stop():
    summary, rows = run_trial("acceleration", True, .1,
                              vehicle_config=trial_config("acceleration", True))
    assert rows[1]["horizontal_speed_mps"] < .1
    assert summary["stopped"] is False
    assert summary["time_to_stop_s"] is None
    assert summary["stopping_path_distance_m"] is None


def test_braking_stop_still_records_first_low_speed_tick():
    summary, rows = run_trial("asphalt-brake", True, 6,
                              vehicle_config=trial_config("asphalt-brake", True))
    first_stop = next(row for row in rows[1:] if row["horizontal_speed_mps"] < .1)
    assert summary["stopped"] is True
    assert summary["time_to_stop_s"] == pytest.approx(first_stop["time_s"])
    assert summary["stopping_path_distance_m"] == pytest.approx(first_stop["path_distance_m"])
