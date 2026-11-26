"""真实撞击回归：细分碰撞拍，普通驾驶仍沿用原积分。"""

import math

import pytest
from panda3d.core import Vec3

import simulation as simulation_module
import tire_drivetrain
from driver_assist import SIMULATION_INPUT
from driving_modes import DrivingMode
from simulation import FIXED_DT, Control, Simulation
from vehicle_designs import vehicle_design
from wheel_dynamics import _solve_force, _solve_rolling_force


@pytest.mark.parametrize('design,vx,vy', [
    ('game-tuned', 8., 12.), ('subaru-wrx-sti', 22., 35.), ('subaru-wrx-sti', 35., 0.)])
@pytest.mark.parametrize('braking', [False, True])
def test_real_rail_impact_completes_with_unchanged_tick_and_hardware(design, vx, vy, braking, monkeypatch):
    config = DrivingMode.GAME.configured_vehicle(base_config=vehicle_design(design).config)
    simulation = Simulation(track='highway', traffic_count=0, config=config)
    calls, impacts = [], []
    advance = simulation_module.advance_world

    def observed(*args, **kwargs):
        calls.append(kwargs['substeps'])
        return advance(*args, **kwargs)

    monkeypatch.setattr(simulation_module, 'advance_world', observed)
    try:
        simulation.reset_player((5.8, 30., .55))
        simulation.player._chassis.setLinearVelocity(Vec3(vx, vy, 0))
        simulation.player.tires.initialize_rolling(vy)
        for _ in range(240):
            simulation.step(Control(brake=float(braking), throttle=float(not braking)))
            impacts.extend(simulation.snapshot().impacts)
        state = simulation.snapshot()
        assert impacts and any(event.raw_impulse > 0 for event in impacts)
        assert state.tick == 240 and state.time == 240*FIXED_DT
        assert max(calls) == 4 and simulation.config is config
        assert simulation.player_collisions > 0
    finally:
        simulation.close()


def test_clear_road_does_not_predict_contact_and_uses_single_step(monkeypatch):
    config = DrivingMode.GAME.configured_vehicle(base_config=vehicle_design('game-tuned').config)
    simulation = Simulation(track='highway', traffic_count=0, config=config)
    calls = []
    advance = simulation_module.advance_world

    def observed(*args, **kwargs):
        calls.append(kwargs['substeps'])
        return advance(*args, **kwargs)

    def unexpected():
        pytest.fail('游戏模式仍在预测碰撞')

    monkeypatch.setattr(simulation_module, 'advance_world', observed)
    monkeypatch.setattr(simulation, '_approaching_body_contact', unexpected)
    try:
        for _ in range(240):
            simulation.step(Control(throttle=1.))
        assert calls == [1] * 240
    finally:
        simulation.close()


def test_distant_traffic_keeps_actuators_across_refined_substeps(monkeypatch):
    simulation = Simulation(track='highway', traffic_count=1, config=DrivingMode.GAME.configured_vehicle())
    npc = simulation.npcs[0]
    stages = npc.physics_stages
    calls = []

    def observed(request, dt):
        calls.append(dt)
        return stages(request, dt)

    monkeypatch.setattr(npc, 'physics_stages', observed)
    try:
        position = npc._chassis.getTransform().getPos()
        player_pos = simulation.player._chassis.getTransform().getPos()
        assert (position - player_pos).lengthSquared() > 1600.
        simulation._impact_events = (object(),)
        simulation.step(Control(), traffic_controls=(Control(throttle=1.),))
        assert calls == [FIXED_DT / 4]
        assert npc._native_request is not None and npc.native_dt == FIXED_DT / 4
    finally:
        simulation.close()


def test_impact_window_and_last_resort_cover_only_the_failed_substep(monkeypatch, caplog):
    config = DrivingMode.GAME.configured_vehicle()
    simulation = Simulation(track='test', traffic_count=0, config=config)
    solve = tire_drivetrain.joint_solve
    substeps = []

    def fail_once(*args):
        substeps.append(1)
        if len(substeps) == 2:
            raise ArithmeticError('测试凸体失败')
        return solve(*args)

    monkeypatch.setattr(tire_drivetrain, 'joint_solve', fail_once)
    try:
        simulation._impact_events = (object(),)
        with caplog.at_level('DEBUG', logger='simulation'):
            for count in (4,) * 6 + (2,) * 10 + (1,):
                before = len(substeps)
                simulation.step(Control())
                assert len(substeps) - before == count
        assert simulation.snapshot().tick == 17
        assert caplog.text.count('刚体阻尼推进') == 1
    finally:
        simulation.close()


@pytest.mark.parametrize('strict', [False, True])
def test_first_python_sweep_failure_is_passive_only_in_game(monkeypatch, strict):
    options = {'input_config': SIMULATION_INPUT} if strict else {}
    simulation = Simulation(track='test', traffic_count=0, config=DrivingMode.GAME.configured_vehicle(), **options)

    def fail(*args):
        raise ArithmeticError('共同末状态不可用')

    monkeypatch.setattr(tire_drivetrain, 'native_contact_geometry', lambda *args, **kwargs: None)
    monkeypatch.setattr(tire_drivetrain, 'shared_load_solution', fail)
    try:
        stages = simulation.player.physics_stages(simulation.player.prepare_control(Control(throttle=1.)), FIXED_DT)
        request = next(stages)
        if strict:
            with pytest.raises(ArithmeticError, match='共同末状态不可用'):
                request.solve()
        else:
            result = request.solve()
            assert result.sweeps == 0 and result.engine_work == 0.
            assert result.engine_body_torque == result.shaft_body_torque == (0., 0., 0.)
            assert all(w.fx == w.fy == w.brake_torque == 0. and math.isfinite(w.omega) for w in result.wheels)
            with pytest.raises(StopIteration):
                stages.send(result)
    finally:
        simulation.close()


def test_python_fallback_keeps_lowest_residual_completed_sweep(monkeypatch):
    config = DrivingMode.GAME.configured_vehicle()
    simulation = Simulation(track='test', traffic_count=0, config=config)
    native_residuals = tire_drivetrain.wheel_residuals
    trials = iter((12., 1.25, 9.))

    def residual(*args):
        native_residuals(*args)
        error = next(trials, None)
        if error is None:
            raise ArithmeticError('修正试探失败')
        return error, 0.

    monkeypatch.setattr(tire_drivetrain, 'native_contact_geometry', lambda *args, **kwargs: None)
    monkeypatch.setattr(tire_drivetrain, 'wheel_residuals', residual)
    monkeypatch.setattr(tire_drivetrain, 'suspension_residuals', lambda *args: (0., 0.))
    try:
        stages = simulation.player.physics_stages(simulation.player.prepare_control(Control()), FIXED_DT)
        result = next(stages).solve()
        assert result.sweeps == 4
        assert all(w.residual == 1.25 for w in result.wheels)
        stages.close()
    finally:
        simulation.close()


@pytest.mark.parametrize('rolling', [False, True])
def test_singular_game_root_returns_best_bounded_trial(rolling):
    def residual(fx, fy):
        return fx - 4., fy - 4.

    def jacobian(fx, fy):
        return (1., 0., 0., 1.) if fx == fy == 0. else (0., 0., 0., 0.)

    if rolling:
        fx, fy, error = _solve_rolling_force(residual, jacobian, 2., .1, game_solver_tolerance=True)
    else:
        fx, fy, error = _solve_force(residual, .1, jacobian=jacobian, grip=2.)
        with pytest.raises(ZeroDivisionError):
            _solve_force(residual, .1, jacobian=jacobian, initial=(1., 1.))
    assert math.hypot(fx, fy) <= 2.
    assert error == pytest.approx(math.sqrt(32.) - 2.)
