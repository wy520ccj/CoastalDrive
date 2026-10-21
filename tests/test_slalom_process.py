"""独立权威物理进程实际运行完整过门，验证新结果与记录回传。"""

import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/"tools"))
from slalom_driver import SlalomDriver

from driving_modes import DrivingMode
from race import BestTimes, GameMode
from session import Phase
from session_process import SessionProcess


def test_independent_process_completes_real_slalom_and_keeps_best_on_restart(tmp_path):
    app = SessionProcess(track="endless", road_shape="straight", driving_mode=DrivingMode.GAME,
                         scores=BestTimes(tmp_path/"best.json"), independent_clock=True)
    try:
        app.start(countdown=False, mode=GameMode.SLALOM_LESSON, settle_initial=True)
        app.set_controller(SlalomDriver(60., app.vehicle_config, origin=8.))
        deadline = time.monotonic()+80.
        while time.monotonic() < deadline and app.phase != Phase.RESULTS:
            app.frame(0.)
            time.sleep(.01)
        result = app.highway.snapshot.slalom
        assert app.phase == Phase.RESULTS and result.succeeded and result.gates == 6
        assert result.medal == "金" and app.current.collisions == 0 and app.current.tick > 1200
        assert len(result.gate_times) == 6 and result.gate_times[-1] == result.run_seconds
        assert result.new_best and not result.reference_times
        app.start(countdown=False, mode=GameMode.SLALOM_LESSON)
        assert app.highway.snapshot.slalom.best_seconds == result.run_seconds
        assert app.highway.snapshot.slalom.reference_times == result.gate_times
    finally:
        app.close()


def test_independent_process_practice_continues_misses_without_saving_medal(tmp_path):
    app = SessionProcess(track='endless', road_shape='straight', driving_mode=DrivingMode.GAME,
                         scores=BestTimes(tmp_path/'best.json'), independent_clock=True)
    try:
        app.start(countdown=False, mode=GameMode.SLALOM_PRACTICE, settle_initial=True)
        app.set_controller(SlalomDriver(35., app.vehicle_config, origin=8., straight=True))
        deadline = time.monotonic()+65.
        while time.monotonic() < deadline and app.phase != Phase.RESULTS:
            app.frame(0.)
            time.sleep(.01)
        result = app.highway.snapshot.slalom
        assert app.phase == Phase.RESULTS and result.practice and result.succeeded
        assert result.entry_kph < 40 and result.gates == 1 and len(result.gate_times) == 6
        assert not result.medal and not result.new_best
        assert not (tmp_path/'slalom-best.json').exists()
    finally:
        app.close()
