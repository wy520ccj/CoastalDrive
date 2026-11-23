"""真实控件的逐层返回；展开说明不能丢失选择或改动试验。"""

from panda3d.core import Point2, Point3

from lab_application import VehicleLab


def test_details_and_naming_return_one_level_without_losing_draft(tmp_path, monkeypatch):
    monkeypatch.setenv('LOCALAPPDATA', str(tmp_path/'user'))
    app = VehicleLab(offscreen=True, output=tmp_path/'reports', scheme_root=tmp_path/'schemes')
    app.engine.taskMgr.remove('lab-update')
    try:
        app.entries['cg'].enterText('.46')
        panel = app.workshop
        panel.show()
        panel.action('challenge-tab', 2)
        panel.action('challenge-value', ('brake_share', '70'))
        entry = panel.editor.challenge_entries['brake_share']
        entry['focus'] = 1
        app.escape()
        assert not entry['focus'] and not panel.root.isHidden()
        assert panel.draft.brake_share == .7
        assert app.run_state is None and app.record is None
        app.escape()
        assert panel.root.isHidden()

        app.schemes.show()
        app.schemes.toggle_save()
        app.schemes.name_entry.enterText('保留这个名字')
        app.schemes.name_entry['focus'] = 1
        app.escape()
        assert app.schemes.save_panel.isHidden() and not app.schemes.root.isHidden()
        assert not app.schemes.name_entry.guiItem.getFocus()
        assert app.schemes.name_entry.get() == '保留这个名字'
        app.schemes.toggle_details()
        app.escape()
        assert app.schemes.details.isHidden() and not app.schemes.root.isHidden()
        app.escape()
        assert app.schemes.root.isHidden()
        assert app.entries['cg'].get() == '.46'
        assert app.run_state is None and app.record is None and app.workspace_vehicle is None
    finally:
        app.close_game()


def test_preview_and_repeated_replay_framing_show_whole_car(tmp_path):
    app = VehicleLab(offscreen=True, output=tmp_path/'reports')
    app.engine.taskMgr.remove('lab-update')
    try:
        for _ in range(3):
            app.resize()
            app.scene.frame_vehicle()
            for part in (app.scene.vehicle, *app.scene.wheels):
                lower, upper = part.getTightBounds(app.scene.root)
                for x in (lower.x, upper.x):
                    for y in (lower.y, upper.y):
                        for z in (lower.z, upper.z):
                            point = app.engine.cam.getRelativePoint(app.scene.root, Point3(x, y, z))
                            projected = Point2()
                            assert app.engine.camLens.project(point, projected)
                            assert abs(projected.x) < .98 and abs(projected.y) < .98
        assert app.run_state is None
    finally:
        app.close_game()
