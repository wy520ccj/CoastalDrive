"""真实低速键盘穿过原Double舍入停滞点；不移动或简化车辆。"""

from route_driver import RouteDriver
from slalom_driver import apply_keys

from application import CoastalDrive
from race import GameMode
from session import Phase
from simulation import Control


def test_low_speed_coastal_keyboard_does_not_stall_shared_root(tmp_path):
    app = CoastalDrive(smoke=True, output=tmp_path, render_size=(320, 180))
    app.taskMgr.remove("finish-smoke")
    app.taskMgr.remove("drive-update")
    try:
        app.back_to_menu()
        app.start_game(mode=GameMode.TIME_TRIAL)
        for _ in range(360):
            app.session.tick()
        app.session.set_controller(app.session.keyboard)
        driver = RouteDriver(35.)
        for _ in range(1200):
            desired = driver.sample(app.session.current, 1/120)
            control = Control(steering=0. if abs(desired.steering) < .06 else (1. if desired.steering > 0 else -1.),
                              throttle=float(desired.throttle > .30), brake=float(desired.brake > .25))
            apply_keys(app.session.keyboard, control)
            app.session.tick()
        assert app.session.phase == Phase.DRIVING and app.session.current.collisions == 0
        assert not app.session.race.snapshot.invalidated
    finally:
        app.close_game()
