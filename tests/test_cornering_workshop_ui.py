"""真实工坊控件的选题、定圆A/B、取消与持久化交接。"""

from types import SimpleNamespace

import pytest
from direct.gui import DirectGuiGlobals as DGG

import workshop_cornering as cornering
from lab_application import VehicleLab
from vehicle_workspace import WorkspaceVehicle


@pytest.fixture
def lab(tmp_path):
    app = VehicleLab(offscreen=True, output=tmp_path/"reports")
    app.engine.taskMgr.remove("lab-update")
    yield app
    app.close_game()


def finish(app):
    while app.workshop.phase is not None:
        while not app.run_state.done:
            app.run_state.step()
        app.update(SimpleNamespace(cont=None))


def test_real_gold_result_survives_workspace_and_topic_switch_but_changed_selection_invalidates(lab):
    panel = lab.workshop
    panel.show()
    panel.topic_menu.set(1)
    assert panel.topic == 1 and not panel.lower_cg.isHidden()
    assert "40m" in panel.rules.getText() and "峰值侧偏" in panel.rules.getText()
    assert panel.share.component("item0")["text_font"] == lab.font
    assert panel.brakes.component("item0")["text_font"] == lab.font
    panel.share.set(2)
    panel.start()
    assert panel.topic_menu["state"] == DGG.DISABLED
    finish(lab)
    assert panel.result["passed"] and panel.result["medal"] == "金"
    assert panel.drive_button["state"] == DGG.NORMAL
    assert "路径跟踪" in panel.feedback.getText()
    saved = lab.capture_workspace()
    panel.topic_menu.set(0)
    assert panel.topic == 0 and panel.lower_cg.isHidden() and panel.result is None
    assert panel.share.component("item0")["text_font"] == lab.font
    panel.restore(saved.workshop_state)
    assert panel.topic == 1 and panel.selection() == (2, False, False)
    assert panel.result["passed"] and panel.drive_button["state"] == DGG.NORMAL
    panel.lower_cg.set(1)
    assert panel.result is None and panel.selected_cost() == 5
    assert "超出预算" in panel.budget.getText() and panel.drive_button["state"] == DGG.DISABLED


def test_sharp_recipe_is_rejected_and_changing_topic_cancels_an_active_trial(lab):
    panel = lab.workshop
    panel.topic_menu.set(1)
    panel.share.set(3)
    panel.start()
    finish(lab)
    assert not panel.result["passed"] and "侧偏" in panel.feedback.getText()
    assert panel.drive_button["state"] == DGG.DISABLED
    baseline, candidate = panel.baseline, panel.candidate
    panel.show()
    panel.show_insights()
    assert panel.insights.data['rows'][0][2] > 4
    assert panel.insights.metric_rows[3][0].getText() == '末窗平均实际转角 / °'
    assert panel.insights.metric_rows[0][2].getText() == f"{panel.insights.data['rows'][0][2]:.3f}"
    assert panel.insights.prepare['state'] == DGG.NORMAL
    panel.prepare_next_trial()
    assert panel.selection() == (2, False, False) and panel.result is None and panel.phase is None
    assert panel.baseline is baseline and panel.candidate is candidate
    panel.start()
    run = lab.run_state
    panel.set_topic(0)
    assert run.paused and panel.phase is None and panel.result is None
    assert panel.topic_menu["state"] == DGG.NORMAL


def test_save_uses_measured_config_and_restart_restores_the_correct_topic(lab, tmp_path, monkeypatch):
    panel = lab.workshop
    panel.set_topic(1)
    panel.share.set(2)
    panel.start()
    finish(lab)
    blocked = tmp_path/"blocked"
    blocked.write_text("file", encoding="utf-8")
    monkeypatch.setattr("vehicle_workspace.workspace_vehicle_path", lambda: blocked/"vehicle.json")
    panel.drive()
    assert lab.next_workspace is None and panel.result["passed"]
    lab.notice.dismiss()
    target = tmp_path/"vehicle.json"
    monkeypatch.setattr("vehicle_workspace.workspace_vehicle_path", lambda: target)
    monkeypatch.setattr(lab, "userExit", lambda: None)
    lab.entries["cg"].enterText(".9")
    panel.drive()
    vehicle = WorkspaceVehicle.load(target)
    assert lab.next_workspace == "game" and lab.next_drive
    assert vehicle.config == cornering.build_config(2, False, False)
    assert vehicle.workshop_result["challenge_id"] == cornering.CHALLENGE_ID
    lab.record, lab.baseline = panel.candidate, panel.baseline
    panel.set_topic(0)
    panel.restore_saved(vehicle)
    assert panel.topic == 1 and panel.selection() == (2, False, False)
    assert panel.result["medal"] == "金"


def test_repeated_topic_switch_releases_old_controls_and_keeps_popup_fonts(lab):
    panel = lab.workshop
    panel.set_topic(1)
    count = panel.root.getNumChildren()
    for index in range(20):
        panel.set_topic(index % 2)
        assert panel.root.getNumChildren() == count
        for menu in (panel.share, panel.brakes):
            assert menu.component("item0")["text_font"] == lab.font
            menu.showPopupMenu()
            menu.hidePopupMenu()
