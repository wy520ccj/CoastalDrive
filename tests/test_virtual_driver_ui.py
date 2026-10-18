"""实际方案库入口、A/B道路完成、原实验保留与取消/错误出口。"""

import gzip
import json
from pathlib import Path

import pytest
from direct.gui import DirectGuiGlobals as DGG

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
    finish(panel)
    assert panel.comparison.status == "complete" and panel.comparison.run.closed
    assert "有效用时" in panel.columns[0].getText() and "B−A" in panel.columns[3].getText()
    assert panel.report.is_file() and lab.entries["cg"].get() == ".48"
    assert all(path.read_bytes() == data for path, data in original_files.items())
    assert not list(lab.scheme_root.parent.rglob("*best*.json"))
    summary = json.loads((panel.report.parent/"comparison.json").read_text(encoding="utf-8"))
    assert summary["updates_player_progress"] is False
    panel.hide()
    assert not lab.schemes.root.isHidden() and panel.root.isHidden()
    assert lab.record.snapshots == record.snapshots


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
