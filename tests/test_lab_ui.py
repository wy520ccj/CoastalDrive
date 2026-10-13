"""时间轴与工作方式切换的所有权；真实图形另由lab_ui_check验证。"""

from types import SimpleNamespace

from lab_application import VehicleLab
from ui.lab_widgets import LabOptionMenu


def test_menu_hover_does_not_shrink_hitbox_or_change_text_size():
    item = {"frameSize": (0, .60, -.04, .04), "text_scale": (.038, .038),
            "frameColor": (1, 1, 1, 1)}
    menu = {"highlightColor": (.85, .91, .91, 1)}
    class HoverMenu(dict):
        highlightedIndex = None

    fake = HoverMenu(menu)
    for _ in range(20):
        LabOptionMenu._highlightItem(fake, item, 2)
        assert fake.highlightedIndex == 2
        assert item["frameSize"] == (0, .60, -.04, .04)
        assert item["text_scale"] == (.038, .038)
        LabOptionMenu._unhighlightItem(fake, item, (1, 1, 1, 1))
        assert fake.highlightedIndex is None
    assert item["frameColor"] == (1, 1, 1, 1)


def test_programmatic_slider_events_do_not_pause_computation_and_user_scrub_does():
    shown = []
    run = SimpleNamespace(paused=False)
    fake = SimpleNamespace(_seeking=False, pointer_pressed=False,
        run_state=run, timeline={"value": .25}, show_sample=shown.append)
    VehicleLab.seek(fake)
    assert not run.paused and shown == []
    fake.pointer_pressed = True
    VehicleLab.seek(fake)
    assert run.paused and shown == [30]


def test_switch_requests_exit_and_cleanup_releases_world_once():
    calls = []
    fake = SimpleNamespace(next_workspace=None, userExit=lambda: calls.append("exit"))
    VehicleLab.back_to_game(fake)
    assert fake.next_workspace == "game" and calls == ["exit"]
    fake = SimpleNamespace(_closed=False, taskMgr=SimpleNamespace(remove=lambda _: None),
        ignoreAll=lambda: None, run_state=SimpleNamespace(close=lambda: calls.append("world-close")),
        scene=SimpleNamespace(close=lambda: calls.append("scene-close")),
        root=SimpleNamespace(destroy=lambda: None), destroy=lambda: calls.append("window-close"))
    VehicleLab.close_game(fake)
    VehicleLab.close_game(fake)
    assert calls.count("world-close") == 1
    assert calls.index("world-close") < calls.index("window-close")
