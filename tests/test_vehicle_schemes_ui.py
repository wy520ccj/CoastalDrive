"""真实方案控件：多配方保存、比较、恢复、试驾与坏记录保留。"""

from types import SimpleNamespace

import pytest
from direct.gui import DirectGuiGlobals as DGG

import workshop_cornering as cornering
from lab_application import VehicleLab
from vehicle_schemes import list_schemes, load_scheme
from vehicle_workspace import WorkspaceVehicle


@pytest.fixture
def lab(tmp_path):
    app = VehicleLab(offscreen=True, output=tmp_path/"reports", scheme_root=tmp_path/"schemes")
    app.engine.taskMgr.remove("lab-update")
    yield app
    app.close_game()


def trial(app, index):
    panel = app.workshop
    panel.set_topic(1)
    panel.share.set(index)
    panel.start()
    while panel.phase is not None:
        while not app.run_state.done:
            app.run_state.step()
        app.update(SimpleNamespace(cont=None))
    assert panel.result is not None
    return panel.candidate


def save(app, name):
    app.schemes.show()
    app.schemes.name_entry.enterText(name)
    app.schemes.save_current()
    return app.schemes.selected(1)


def test_two_real_recipes_compare_load_and_drive_frozen_hardware(lab, tmp_path, monkeypatch):
    panel = lab.schemes
    panel.show()
    assert panel.drive_button["state"] == DGG.DISABLED
    trial(lab, 1)
    a = save(lab, "轻预算45k")
    panel.hide()
    trial(lab, 2)
    b = save(lab, "循迹50k")
    assert len(panel.schemes) == 2
    assert "B−A" in panel.comparison.getText() and "峰值侧偏" in panel.comparison.getText()
    assert "铜牌" in panel.left_text.getText() and "金牌" in panel.right_text.getText()
    assert panel.menus[1].component("item0")["text_font"] == lab.font
    panel.show_curves()
    assert panel.root.isHidden()
    assert lab.baseline.snapshots == a.records()[1].snapshots
    assert lab.record.snapshots == b.records()[1].snapshots
    assert lab.workshop.baseline.snapshots == b.records()[0].snapshots
    # 曲线A改为另一方案，不应使工坊原始A基线丢失或失去奖牌。
    assert lab.workshop.result["medal"] == "金"
    panel.show()
    panel.load_right()
    assert lab.engineered_config == cornering.build_config(2, False, False)
    assert lab.workshop.selection() == (2, False, False)
    path = tmp_path/"current.json"
    monkeypatch.setattr("vehicle_workspace.workspace_vehicle_path", lambda: path)
    monkeypatch.setattr(lab, "userExit", lambda: None)
    lab.entries["cg"].enterText(".9")
    panel.drive_right()
    current = WorkspaceVehicle.load(path)
    assert current.scheme_id == b.id and current.config == b.vehicle.config
    assert lab.next_workspace == "game" and lab.next_drive
    assert lab.capture_workspace().record.snapshots == b.records()[1].snapshots
    assert not load_scheme(lab.scheme_root, a.id).vehicle.workshop_result["road_validated"]
    panel.schemes = []
    panel.indices = [0, 0]
    panel.refresh()
    assert panel.selected(1).id == b.id
    # 左侧比较记录损坏，不能阻止使用仍完整的右侧方案。
    (a.folder/"trial"/"snapshots.bin").write_bytes(b"bad")
    panel.present()
    assert panel.curves_button["state"] == DGG.DISABLED
    assert panel.load_button["state"] == panel.drive_button["state"] == DGG.NORMAL


def test_failed_recipe_is_saved_for_analysis_without_forged_award(lab):
    trial(lab, 3)
    item = save(lab, "侧偏超限")
    assert item.vehicle.workshop_result is None and not item.challenge["passed"]
    assert "未获工坊" in lab.schemes.right_text.getText()
    lab.schemes.load_right()
    assert lab.workshop.result is not None and not lab.workshop.result["passed"]
    assert lab.workshop.drive_button["state"] == DGG.DISABLED


def test_missing_record_and_write_failure_preserve_trial_and_other_schemes(lab, tmp_path, monkeypatch):
    candidate = trial(lab, 2)
    item = save(lab, "好方案")
    blocked = tmp_path/"blocked"
    blocked.write_text("file", encoding="utf-8")
    lab.scheme_root = blocked/"schemes"
    lab.schemes.save_current()
    assert lab.active_record().snapshots == candidate.snapshots
    assert lab.next_workspace is None
    lab.notice.dismiss()
    lab.scheme_root = item.folder.parent
    (item.folder/"trial"/"snapshots.bin").write_bytes(b"bad")
    before = lab.record
    lab.schemes.load_right()
    assert lab.record is before and lab.next_workspace is None
    lab.schemes.present()
    assert lab.schemes.drive_button["state"] == DGG.DISABLED
    assert "不可用" in lab.schemes.comparison.getText()


def test_more_than_six_schemes_have_stable_paging_popup_and_focus(lab):
    trial(lab, 1)
    for index in range(8):
        save(lab, f"方案{index}")
    panel = lab.schemes
    assert panel.indices[1] == 7
    count = panel.root.getNumChildren()
    for _ in range(10):
        panel.move(1, 1)
        assert panel.root.getNumChildren() == count
        assert panel.menus[1].component("item0")["text_font"] == lab.font
        panel.menus[1].showPopupMenu()
        panel.menus[1].hidePopupMenu()
    panel.name_entry["focus"] = 1
    lab.escape()
    assert panel.root.isHidden() and not panel.name_entry.guiItem.getFocus()
    assert len(list_schemes(lab.scheme_root)[0]) == 8
