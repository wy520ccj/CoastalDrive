"""新赛事ID进入独立权威进程，快照和暂停边界正常回传。"""

import time

from driving_modes import DrivingMode
from race import GameMode
from session import Phase
from session_process import SessionProcess
from vehicle_designs import vehicle_design


def test_independent_career_start_input_and_pause():
    session = SessionProcess(track='endless', physics_workers=0, driving_mode=DrivingMode.GAME,
                             vehicle_config=vehicle_design('reference-rwd').config)
    try:
        session.start(mode=GameMode.CAREER, track='endless', career_event_id='first-drive',
                      countdown=False, settle_initial=True)
        assert not session.current.traffic and session.highway.snapshot.career.event_id == 'first-drive'
        initial = session.current.tick
        session.keyboard.press('w')
        deadline = time.monotonic()+6.
        while session.frame(0).tick < initial+36 and time.monotonic() < deadline:
            time.sleep(.005)
        session.pause()
        assert session.phase == Phase.PAUSED and session.current.tick >= initial+36
        assert session.highway.snapshot.career.elapsed > 0 and 0 < session.current.player.throttle <= 1.
        assert session.highway.snapshot.career.position > 0
        stopped = session.current
        assert session.frame(1) == stopped
        session.menu()
        session.start(mode=GameMode.CAREER, track='endless', career_event_id='parking')
        assert session.highway.snapshot.career.event_id == 'parking'
        assert not session.current.traffic
        session.start(countdown=False)
        assert session.highway.snapshot.career.event_id == 'parking'
    finally:
        session.close()
