"""实际方案库入口、A/B道路完成、原实验保留与取消/错误出口。"""

import gzip
import json
from pathlib import Path

import pytest
from direct.gui import DirectGuiGlobals as DGG
from road_review_check import SavedComparison, archived_records

from lab_application import VehicleLab
from lab_experiment import LabOptions
from vehicle_schemes import list_schemes

ROOT = Path(__file__).resolve().parents[1]


def seed_library(target):
    source = ROOT/"docs/evidence/DESIGN-SCHEMES-01/normal/schemes"
    for path in source.rglob("*"):
        if not path.is_file():
            continue
        dest = target/path.relative_to(source)
        dest = dest.with_suffix("") if path.suffix == ".gz" else dest
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(gzip.decompress(path.read_bytes()) if path.suffix == ".gz" else path.read_bytes())
    return list_schemes(target)[0]


@pytest.fixture
def lab(tmp_path, monkeypatch):
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path/"user"))
    app = VehicleLab(offscreen=True, output=tmp_path/"reports", scheme_root=tmp_path/"schemes")
    app.engine.taskMgr.remove("lab-update")
    seed_library(app.scheme_root)
    yield app
    app.close_game()


def prepare(app):
    app.schemes.show()
    app.schemes.indices = [0, 1]
    app.schemes.build_menu(0)
    app.schemes.build_menu(1)
    app.schemes.present()
    panel = app.schemes.virtual_driver
    panel.show()
    return panel


def finish(panel):
    while not panel.comparison.done:
        panel.update()


def test_actual_road_comparison_preserves_trial_draft_and_player_progress(lab):
    lab.set_options(LabOptions(duration=.1, speed_kph=20))
    lab.start_experiment()
    while not lab.run_state.done:
        lab.run_state.step()
    old_run, record = lab.run_state, lab.active_record()
    lab.entries["cg"].enterText(".48")
    panel = prepare(lab)
    original_files = {p: p.read_bytes() for p in lab.scheme_root.rglob("*") if p.is_file()}
    panel.start()
    assert old_run.closed and lab.run_state is None and lab.record.snapshots == record.snapshots
    assert panel.run_button["state"] == DGG.DISABLED
    saw_left = False
    while not panel.comparison.done:
        panel.update()
        if len(panel.comparison.records) == 1 and not panel.comparison.done:
            saw_left = True
            assert '试车中' in panel.result_labels[1].getText()
            assert panel.metric_rows[1][1].getText() != '待完成'
            assert panel.metric_rows[1][2].getText() == '待完成'
            assert len(panel.paths) == 1
    assert saw_left
    assert panel.comparison.status == "complete" and panel.comparison.run.closed
    assert "有效用时" in panel.metric_rows[0][0].getText() and "变化" in panel.metric_headers[3].getText()
    assert panel.report.is_file() and lab.entries["cg"].get() == ".48"
    assert all(path.read_bytes() == data for path, data in original_files.items())
    assert not list(lab.scheme_root.parent.rglob("*best*.json"))
    summary = json.loads((panel.report.parent/"comparison.json").read_text(encoding="utf-8"))
    assert summary["updates_player_progress"] is False
    panel.hide()
    assert not lab.schemes.root.isHidden() and panel.root.isHidden()
    assert lab.record.snapshots == record.snapshots
    panel.show()
    assert '报告已保存' in panel.note.getText()
    panel.start()
    assert '报告已保存' not in panel.note.getText() and panel.report is None
    assert len(panel.paths) == 0 and panel.metric_rows[0][1].getText() == '待完成'
    panel.hide()


def test_escape_cancels_and_closes_world_then_returns_to_scheme_list(lab):
    panel = prepare(lab)
    panel.start()
    panel.comparison.run.step()
    world = panel.comparison.run.simulation
    lab.escape()
    assert world.closed and panel.comparison.status == "cancelled"
    assert len(panel.comparison.records) == 1 and not lab.schemes.root.isHidden()
    panel.show()
    assert panel.save_report()
    assert not (panel.report.parent/"B").exists()
    panel.hide()
    lab.escape()
    assert lab.schemes.root.isHidden()


def test_bad_selected_record_does_not_close_original_lab_world(lab):
    lab.set_options(LabOptions(duration=.1))
    lab.start_experiment()
    old = lab.run_state
    panel = prepare(lab)
    selected = lab.schemes.selected(0)
    (selected.folder/"trial"/"snapshots.bin").write_bytes(b"broken")
    panel.start()
    assert panel.comparison is None and lab.run_state is old and not old.closed


def test_export_failure_keeps_records_and_retries_without_rerunning_physics(lab, tmp_path):
    panel = prepare(lab)
    panel.start()
    panel.comparison.run.step()
    panel.comparison.close()
    panel.present()
    records = panel.comparison.records[:]
    blocked = tmp_path/"blocked"
    blocked.write_text("file", encoding="utf-8")
    lab.output = blocked/"reports"
    assert not panel.save_report() and panel.comparison.run.closed
    lab.output = tmp_path/"retry"
    assert panel.save_report() and panel.comparison.records == records


def test_closing_lab_mid_trial_releases_the_only_road_world(lab):
    panel = prepare(lab)
    panel.start()
    world = panel.comparison.run.simulation
    lab.close_game()
    assert world.closed and panel.comparison.status == "cancelled"


def test_review_scrubs_original_records_without_opening_a_physics_world(lab, monkeypatch):
    import road_comparison
    def forbidden(*args, **kwargs):
        raise AssertionError("复盘不得新建物理世界")
    monkeypatch.setattr(road_comparison, "Simulation", forbidden)
    panel = prepare(lab)
    records = archived_records("normal")
    panel.comparison = SavedComparison(records)
    panel.present()
    assert panel.paths[0].getTightBounds(panel.root)[1].x < panel.point(320., 0.)[0]
    lab.entries["cg"].enterText(".48")
    panel.review_button["command"]()
    review = panel.review
    assert not review.root.isHidden() and review.slider["value"] == 240.
    expected = records[1].metadata["result"]["clearances"][3]
    assert "漏门" in review.details[0].getText() and f"{expected:+.3f}" in review.details[1].getText()
    before = tuple(record.snapshots for record in records)
    review.slider.guiItem.setValue(220.)
    review.slider.commandFunc()
    assert "220.0" in review.readout.getText() and review.slider["value"] == 220.
    for distance in range(321):
        review.slider["value"] = distance
        review.seek()
    review.gate_buttons[5]["command"]()
    assert "未到达" in review.details[0].getText() and "通过" in review.details[1].getText()
    assert lab.run_state is None and lab.entries["cg"].get() == ".48"
    assert before == tuple(record.snapshots for record in records)
    lab.escape()
    assert review.root.isHidden() and not panel.root.isHidden()
    lab.escape()
    assert panel.root.isHidden() and not lab.schemes.root.isHidden()


def test_review_single_partial_and_broken_gate_records_are_explicit(lab):
    from dataclasses import replace
    panel = prepare(lab)
    original = archived_records("normal")[0]
    partial = replace(original, snapshots=original.snapshots[:1], controls=(), rows=(),
        metadata={**original.metadata, "result": {**original.metadata["result"], "clearances": [], "errors": [], "gates": 0},
                  "metrics": {**original.metadata['metrics'], 'gates': 0, 'reason': '已取消',
                              'valid_seconds': None, 'minimum_clearance_m': None}})
    panel.comparison = SavedComparison((partial,))
    panel.present()
    assert panel.metric_rows[1][1].getText() == '0'
    assert panel.metric_rows[1][2].getText() == '待完成'
    assert all(row[3].getText() == '—' for row in panel.metric_rows)
    panel.review.show()
    assert all(button["state"] == DGG.DISABLED for button in panel.review.gate_buttons)
    assert "尚无记录" in panel.review.details[1].getText()
    assert "尚无控制" in panel.review.details[0].getText()
    panel.review.hide()
    panel.comparison = SavedComparison((replace(original, snapshots=original.snapshots[:1], controls=(), rows=()),))
    panel.review.show()
    assert panel.review.root.isHidden() and not panel.root.isHidden()


def test_review_loads_selected_b_back_to_original_reference_trial(lab):
    panel = prepare(lab)
    expected = lab.schemes.selected(1)
    panel.comparison = SavedComparison(archived_records("normal"))
    panel.present()
    panel.review.show()
    baseline, record, _ = expected.records()
    # 使用实际按钮事件；载回的是保存的参考试验，而非道路插值状态。
    panel.review.load_button["command"]()
    assert panel.review.root.isHidden() and panel.root.isHidden() and lab.schemes.root.isHidden()
    assert lab.record.snapshots == record.snapshots and lab.baseline.snapshots == baseline.snapshots
    assert lab.engineered_config == expected.vehicle.config and lab.run_state is None
