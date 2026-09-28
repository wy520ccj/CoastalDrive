from application import CoastalDrive
from race import GameMode


def test_gameplay_scene_is_reused_for_restart_and_closed_on_menu(tmp_path, monkeypatch):
    import application

    real_scene = application.Scene
    created = []

    class CountedScene(real_scene):
        def __init__(self, base):
            super().__init__(base)
            created.append(self)

    monkeypatch.setattr(application, "Scene", CountedScene)
    app = CoastalDrive(smoke=True, output=tmp_path)
    app.taskMgr.remove("finish-smoke")
    try:
        assert len(created) == 1
        tasks = len(app.taskMgr.getAllTasks())
        events = len(app.getAllAccepting())
        app.back_to_menu()
        assert app.scene is None
        assert created[0].render.isEmpty()
        assert len(app.taskMgr.getAllTasks()) == tasks
        assert len(app.getAllAccepting()) == events

        app.start_game(mode=GameMode.FREE_DRIVE)
        assert len(created) == 2
        app.start_game(mode=GameMode.FREE_DRIVE)
        assert len(created) == 2
        assert app.scene is created[1]

        app.back_to_menu()
        assert app.scene is None
        assert created[1].render.isEmpty()
        assert len(app.taskMgr.getAllTasks()) == tasks
        assert len(app.getAllAccepting()) == events
        app.start_highway("straight", mode=GameMode.FREE_DRIVE)
        highway_scene = app.scene
        assert len(created) == 3
        app.start_game(mode=GameMode.DISTANCE_CHALLENGE, track="endless")
        assert app.scene is highway_scene
        assert len(created) == 3
    finally:
        app.close_game()
