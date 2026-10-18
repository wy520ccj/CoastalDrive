"""真实20Hz策略/120Hz道路A/B、完整记录及关闭/失败边界。"""

import json
from dataclasses import replace

import pytest

import road_comparison
import workshop_cornering as cornering
from road_comparison import (
    RoadComparison,
    RoadTrial,
    comparison_rows,
    context_mismatches,
    export_comparison,
)
from snapshot_wire import decode_snapshots
from vehicle_config import CAR
from vehicle_workspace import WorkspaceVehicle
from virtual_test_driver import POLICY, target_x


def vehicle(config):
    return WorkspaceVehicle("reference-rwd", config)


@pytest.fixture(scope="module")
def measured():
    records = []
    for config in (cornering.BASE_CONFIG, cornering.build_config(1, False, False), cornering.build_config(2, False, False)):
        run = RoadTrial(vehicle(config))
        try:
            while not run.done:
                run.step()
            records.append(run.record())
        finally:
            run.close()
    return records


def test_fixed_policy_really_distinguishes_failing_original_and_improved_recipes(measured):
    base, mid, gold = measured
    assert not base.metadata["metrics"]["completed"] and base.metadata["metrics"]["gates"] == 3
    assert base.metadata["metrics"]["valid_seconds"] is None
    assert mid.metadata["metrics"]["completed"] and gold.metadata["metrics"]["completed"]
    assert gold.metadata["metrics"]["minimum_clearance_m"] > mid.metadata["metrics"]["minimum_clearance_m"]
    assert all(item.metadata["updates_player_progress"] is False for item in measured)
    rows = comparison_rows((base, gold))
    assert rows[0]["A"] is None and rows[0]["delta"] is None
    assert rows[1]["delta"] == 3


def test_every_step_and_request_are_kept_decisions_hold_for_six_physics_steps(measured):
    for record in measured:
        assert len(record.snapshots) == len(record.controls)+1 == len(record.rows)+1
        initial = record.snapshots[0]
        for index, (state, row) in enumerate(zip(record.snapshots[1:], record.rows, strict=True), 1):
            assert state.tick == initial.tick+index and row["tick"] == index
            assert state.time-initial.time == pytest.approx(index/120, abs=1e-9)
            assert row["x"] == state.player.position[0]
        for start in range(0, len(record.controls), 6):
            chunk = record.controls[start:start+6]
            assert chunk == (chunk[0],)*len(chunk)
        assert record.metadata["policy"] == POLICY
        assert record.metadata["source_start"] == record.metadata["source_end"]
        assert record.metadata["runtime_start"] == record.metadata["runtime_end"]


def test_original_hardware_environment_and_precision_are_explicit_and_not_mutated(tmp_path):
    config = replace(CAR, road_friction=.6, tire_substeps=2, lateral_stiffness=45678.)
    saved = vehicle(config)
    run = RoadTrial(saved)
    try:
        run.step()
        run.stop("cancelled")
        record = run.record()
        assert saved.config == config and run.config.road_friction == 1.1 and run.config.tire_substeps == 1
        assert run.config.lateral_stiffness == 45678.
        assert record.metadata["original_vehicle"]["config"]["road_friction"] == .6
        assert record.metadata["actual_config"]["road_friction"] == 1.1
        assert record.metadata["end_reason"] == "cancelled"
    finally:
        run.close()


@pytest.mark.parametrize("key", ["source_start", "runtime_start", "policy", "environment", "input_config"])
def test_different_context_never_emits_a_delta(measured, key):
    a, b = measured[1:]
    changed = replace(b, metadata={**b.metadata, key: {"changed": True}})
    assert context_mismatches((a, changed))
    assert all(row["delta"] is None for row in comparison_rows((a, changed)))


def test_a_closes_before_b_opens_and_repeat_same_car_is_deterministic(tmp_path, monkeypatch):
    worlds = []
    native = road_comparison.Simulation
    def make_world(*args, **kwargs):
        assert all(world.closed for world in worlds)
        world = native(*args, **kwargs)
        worlds.append(world)
        return world
    monkeypatch.setattr(road_comparison, "Simulation", make_world)
    comparison = RoadComparison(vehicle(CAR), vehicle(CAR))
    try:
        while not comparison.done:
            comparison.advance(1.)
        assert len(worlds) == 2 and all(world.closed for world in worlds)
        a, b = comparison.records
        assert a.rows == b.rows and a.controls == b.controls
        assert [state.player for state in a.snapshots] == [state.player for state in b.snapshots]
        report = export_comparison(comparison, tmp_path/"report", ("同车A", "同车B"))
        assert report.is_file() and "实际道路轨迹" in report.read_text(encoding="utf-8")
        for side, original in (("A", a), ("B", b)):
            folder = report.parent/side
            document = json.loads((folder/"trial.json").read_text(encoding="utf-8"))
            states, _ = decode_snapshots((folder/"snapshots.bin").read_bytes())
            assert states == original.snapshots and len(document["controls"]) == len(states)-1
    finally:
        comparison.close()


def test_cancel_keeps_partial_without_creating_b_or_touching_player_progress(tmp_path, monkeypatch):
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path/"user"))
    comparison = RoadComparison(vehicle(CAR), vehicle(CAR))
    for _ in range(12):
        comparison.run.step()
    comparison.close()
    assert comparison.done and comparison.status == "cancelled" and comparison.run.simulation.closed
    assert len(comparison.records) == 1 and len(comparison.records[0].controls) == 12
    assert comparison_rows(comparison.records) == []
    export_comparison(comparison, tmp_path/"partial", ("A", "B"))
    assert not (tmp_path/"partial"/"B").exists()
    assert not list((tmp_path/"user").rglob("*best*.json"))


def test_physics_failure_and_record_failure_both_close_world(monkeypatch):
    comparison = RoadComparison(vehicle(CAR), vehicle(CAR))
    def failed_step():
        raise RuntimeError("故意的求解失败")
    monkeypatch.setattr(comparison.run, "step", failed_step)
    with pytest.raises(RuntimeError):
        comparison.advance(1.)
    assert comparison.status == "failed" and comparison.run.simulation.closed
    other = RoadComparison(vehicle(CAR), vehicle(CAR))
    def failed_record():
        raise OSError("故意的记录边界失败")
    monkeypatch.setattr(other.run, "record", failed_record)
    with pytest.raises(OSError):
        other.close()
    assert other.run.simulation.closed


def test_path_passes_each_fixed_gate_without_changing_rules():
    from slalom_lesson import GATES
    assert target_x(0) == 0 and target_x(80) == 0
    for y, x in GATES:
        assert target_x(y) == pytest.approx(x)
