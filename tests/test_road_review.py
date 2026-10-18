"""复用双SDK实际道路记录，核对过门、持有请求与只读插值。"""

import math
from dataclasses import replace

import pytest
from road_review_check import SavedComparison, archived_records

from road_comparison import export_comparison
from road_review import focus_position, gate_crossings, sample_at
from slalom_lesson import GATES
from vehicle_config import VehicleConfig, body_center
from vehicle_state import Control


@pytest.fixture(scope="module", params=("normal", "double"))
def records(request):
    return archived_records(request.param)


def test_real_gate_geometry_timing_and_holding_request_match_original_rules(records):
    for record in records:
        gates = gate_crossings(record)
        result = record.metadata["result"]
        assert len(gates) == len(result["clearances"])
        config = VehicleConfig(**record.metadata["actual_config"])
        for index, gate in enumerate(gates):
            yaw = math.radians(gate["heading_deg"])
            span = config.collision_half_width*abs(math.cos(yaw))+config.collision_half_length*abs(math.sin(yaw))
            error = gate["x"]-math.sin(yaw)*body_center(config)[1]-GATES[index][1]
            assert error == result["errors"][index]
            assert 2.-span-abs(error) == gate["clearance_m"] == result["clearances"][index]
            step = gate["completed_tick"]-1
            assert gate["control"]["steering"] == record.controls[step].steering
            assert record.rows[step-1]["time"] <= gate["time"] <= record.rows[step]["time"]
        if result["succeeded"]:
            assert gates[-1]["time"]-result["entry_time"] == result["run_seconds"]
    assert focus_position(records) == 240.


def test_failed_path_is_not_extended_and_reads_leave_original_untouched(records):
    original = tuple(record.snapshots for record in records)
    assert sample_at(records[0], 280.) is None
    assert sample_at(records[1], 320.) is not None
    for record in records:
        assert sample_at(record, -1.) is None
        assert sample_at(record, 0.)["time"] == 0.
        assert sample_at(record, 400.) is None
        for distance in range(321):
            sample_at(record, distance)
    assert original == tuple(record.snapshots for record in records)


def test_partial_and_empty_records_have_no_fake_gates_or_controls(records):
    record = records[0]
    partial = replace(record, snapshots=record.snapshots[:13], rows=record.rows[:12], controls=record.controls[:12],
        metadata={**record.metadata, "result": {**record.metadata["result"], "gates": 0, "errors": [], "clearances": []}})
    assert gate_crossings(partial) == []
    assert focus_position((partial,)) == max(row["position"] for row in partial.rows)
    assert sample_at(partial, 120.) is None
    empty = replace(partial, snapshots=partial.snapshots[:1], rows=(), controls=())
    assert sample_at(empty, 0.)["control"] is None and sample_at(empty, 1.) is None
    assert focus_position((empty,)) == 0. and focus_position(()) == 0.


def test_shortest_heading_wrap_and_first_forward_crossing_are_explicit(records):
    record = records[0]
    initial = record.snapshots[0]
    states = tuple(replace(initial, player=replace(initial.player, heading=heading,
        position=(0., initial.player.position[1]+distance, 0.)))
        for distance, heading in ((0., 179.), (10., -179.), (2., 0.), (10., 5.)))
    rows = tuple({"position": distance, "time": float(index), "tick": index}
                 for index, distance in enumerate((10., 2., 10.), 1))
    short = replace(record, snapshots=states, rows=rows,
                    controls=(Control(steering=.2), Control(steering=.4), Control(steering=.6)))
    sample = sample_at(short, 5.)
    assert sample["heading_deg"] == 180. and sample["time"] == .5
    assert sample["control"]["steering"] == .2 and sample["fraction"] == .5


def test_completed_focus_is_narrowest_gate_and_missing_gate_steps_raise(records):
    record = records[1]
    gates = gate_crossings(record)
    assert focus_position((record,)) == min(gates, key=lambda gate: gate["clearance_m"])["position"]
    broken = replace(record, snapshots=record.snapshots[:1], rows=(), controls=())
    with pytest.raises(ValueError, match="完成步"):
        gate_crossings(broken)


def test_report_keeps_real_gate_table_and_absent_after_failure(records, tmp_path):
    report = export_comparison(SavedComparison(records), tmp_path/"report", ("原配", "方案"))
    page = report.read_text(encoding="utf-8")
    assert "逐门复盘" in page and "未判门 / 无数据" in page and "漏门 / -0.340m" in page
    import json
    document = json.loads((report.parent/"comparison.json").read_text(encoding="utf-8"))
    assert len(document["gate_crossings"][0]) == 4 and len(document["gate_crossings"][1]) == 6
    assert document["gate_crossings"][1][5]["passed"] is True
