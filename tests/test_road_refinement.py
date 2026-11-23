"""加密路面的真实机械回归；保留升级GT、起步时序与原生收敛门槛。"""

import sys
from dataclasses import replace
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'tools/environment'))

from check_driving_composition import ViewDriver

import simulation as simulation_module
from career_tuning import upgraded_config
from driving_modes import DrivingMode
from race import BestTimes, GameMode
from session import Phase, Session
from simulation import FIXED_DT
from vehicle_designs import vehicle_design


def test_upgraded_gt_crosses_reproduced_ridge_support_failure(tmp_path, monkeypatch):
    config = vehicle_design('coastal-gt').config
    for part in ('street-power', 'sport-suspension'):
        config = upgraded_config(config, part)
    config = replace(config, lateral_stiffness=70000.)
    session = Session(0, track='endless', road_shape='ridge-club', vehicle_config=config,
                      scores=BestTimes(tmp_path/'scores.json'))
    advance = simulation_module.advance_world
    substeps = set()

    def observed(*args, **kwargs):
        substeps.add(kwargs['substeps'])
        return advance(*args, **kwargs)

    monkeypatch.setattr(simulation_module, 'advance_world', observed)
    try:
        session.start(countdown=True, mode=GameMode.CAREER, settle_initial=True, career_event_id='ridge-run')
        while session.phase == Phase.COUNTDOWN:
            session.countdown_step(1)
        for _ in range(2):
            session.tick()
        session.set_controller(ViewDriver(session))
        # 原单步在403.814m抛ArithmeticError；实际走过故障区，不能只测细分选择条件。
        for _ in range(6000):
            session.tick()
            distance = session.simulation.road.locate(session.current.player)[0]
            if distance >= 450:
                break
        assert distance >= 450 and session.current.collisions == 0
        assert substeps == {1, 2}
        assert session.current.time == session.current.tick*FIXED_DT
        assert session.base_vehicle_config == config
        assert session.vehicle_config == DrivingMode.GAME.configured_vehicle(base_config=config)
    finally:
        session.close()
