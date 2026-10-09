"""起步动画和后台准备共用会话阶段，未准备好不开放驾驶。"""

from application import CoastalDrive
from session import GameMode, Phase, Session
from simulation import Simulation


def test_countdown_waits_for_resources_and_preserves_pause_and_race_time(monkeypatch):
    ready = False
    monkeypatch.setattr(Simulation,'physics_ready',lambda simulation:ready)
    session = Session()
    try:
        session.start(mode=GameMode.TIME_TRIAL)
        for _ in range(370):
            session.tick()
        assert session.countdown_ticks == 0
        assert session.phase == Phase.COUNTDOWN
        assert session.current.tick == 0
        assert session.race.snapshot.elapsed == 0.
        session.pause()
        assert session.phase == Phase.PAUSED
        session.resume()
        ready = True
        session.tick()
        assert session.phase == Phase.DRIVING
        assert session.current.tick == 0
        assert session.race.snapshot.elapsed == 0.
    finally:
        session.close()


def test_countdown_punch_digits_go_and_menu_are_presentation_only(tmp_path):
    app = CoastalDrive(smoke=True,output=tmp_path)
    app.taskMgr.remove('finish-smoke')
    try:
        animation = app.countdown
        frozen = app.session.current
        for ticks,index in ((360,0),(240,1),(120,2)):
            animation.update('countdown',ticks,1/60)
            assert not animation.root.isHidden()
            assert animation.active == index
            assert animation.labels[index] == str((ticks+119)//120)
            assert not animation.digits[index].isHidden()
            initial = animation.punch.getScale()
            animation.update('countdown',ticks-30,1/60)
            assert animation.punch.getScale() != initial
        animation.update('paused',120,1/60)
        assert animation.root.isHidden()
        animation.update('countdown',120,1/60)
        animation.update('driving',0,1/60)
        assert animation.active == 3
        assert not animation.root.isHidden()
        animation.update('driving',0,.8)
        assert animation.root.isHidden()
        animation.update('menu',0,0.)
        animation.update('driving',0,1/60)
        assert animation.root.isHidden()
        assert app.session.current == frozen
    finally:
        app.close_game()
