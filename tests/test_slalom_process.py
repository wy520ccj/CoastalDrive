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
        app.start(countdown=False, mode=GameMode.SLALOM_LESSON)
        assert app.highway.snapshot.slalom.best_seconds == result.run_seconds
    finally:
        app.close()
