"""工作方式切换覆盖真实窗口所有权、编辑状态和失败出口。"""

from types import SimpleNamespace

from application import CoastalDrive
from session import Phase


def finish(app, target):
    for _ in range(30):
        app.taskMgr.step()
        if app._workspace_steps is None:
            break
    assert app._workspace_steps is None and app.workspace == target


def test_shared_window_keeps_draft_and_releases_previous_world(tmp_path):
    app = CoastalDrive(smoke=True, output=tmp_path, lab_output=tmp_path/"lab")
    app.taskMgr.remove("finish-smoke")
    window, pipeline, world = app.win, app.pipeline, app.session.simulation
    try:
        app.open_vehicle_lab()
        # 请求只显示覆盖层，下一帧才开始释放世界。
        assert not world.closed and not app.workspace_loading.root.isHidden()
        finish(app, "lab")
        assert world.closed and app.session is None
        lab = app.lab
        assert lab.engine is app and not lab.owns_window
        lab.entries["cg"].enterText(".456")
        lab.scene.camera_mode = 2
        lab.back_to_game()
        finish(app, "game")
        assert lab._closed and app.lab is None
        assert app.win is window and app.pipeline is pipeline
        assert app.session.base_vehicle_config == app.workspace_vehicle.config
        assert tuple(app.cam.node().getDisplayRegion(0).getDimensions()) == (0, 1, 0, 1)
        assert abs(app.camLens.getAspectRatio()-app.getAspectRatio()) < 1e-5
        app.open_vehicle_lab()
        finish(app, "lab")
        assert app.lab.entries["cg"].get() == ".456" and app.lab.scene.camera_mode == 2
        assert app.win is window and app.pipeline is pipeline
    finally:
        app.close_game()


def test_loading_failure_retains_opaque_cover_and_exit(tmp_path):
    app = CoastalDrive(smoke=True, output=tmp_path)
    app.taskMgr.remove("finish-smoke")

    def failed_asset():
        yield 0, "准备资源"
        raise OSError("测试资源不可读")

    try:
        app._begin_workspace(failed_asset(), "准备驾驶", "")
        finish(app, "transition")
        assert not app.workspace_loading.root.isHidden()
        assert not app.workspace_loading.exit_button.isHidden()
        assert "加载未完成" in app.workspace_loading.stage.getText()
        assert app.workspace_loading.history[-1][0] == 0
    finally:
        app.close_game()


def test_ready_session_receives_current_focus_when_loading_had_no_window_event():
    observed = []
    session = SimpleNamespace(phase=Phase.LOADING, focus_changed=observed.append)
    properties = SimpleNamespace(getForeground=lambda: False, getMinimized=lambda: False)
    app = SimpleNamespace(workspace="game", _workspace_steps=iter(()), smoke=False,
        session=session, win=SimpleNamespace(getProperties=lambda: properties),
        workspace_loading=SimpleNamespace(resize=lambda: None, hide=lambda: observed.append("hidden")),
        setup_controls=lambda: None, taskMgr=SimpleNamespace(add=lambda *args: None),
        update=lambda task: None, refresh_panel=lambda: None)
    task = SimpleNamespace(frame=1, done="done")
    assert CoastalDrive._advance_workspace(app, task) == "done"
    assert session.phase == Phase.COUNTDOWN and observed == [False, "hidden"]
