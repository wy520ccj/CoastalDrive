"""护栏真实查询保留原世界锁，机械内核和异常可恢复复用。"""

import pytest
from mechanical_kernels import dot
from wheel_contact_kernels import (
    _joint_contact_state,
    _joint_coordinates,
    joint_contact_queries_world,
    joint_contact_query_prepare,
)

import tire_drivetrain
from driving_modes import DrivingMode
from simulation import Control, Simulation


def test_query_packet_preserves_results_and_original_exception():
    expected = (((1., 2., 3., 4., 5., 6.),) * 4, (None, .8, .9, 1.), (False, True, True, True))
    calls = []

    def query(velocity, angular, dt):
        calls.append((velocity, angular, dt))
        return expected

    packet = joint_contact_query_prepare(query)
    assert joint_contact_queries_world(packet)
    assert _joint_contact_state(packet, (1., 2., 3.), (.1, .2, .3), 1 / 120)[:3] == expected
    assert calls == [((1., 2., 3.), (.1, .2, .3), 1 / 120)]
    failure = ValueError('原护栏查询错误')

    def failed(*args):
        raise failure

    with pytest.raises(ValueError) as caught:
        _joint_contact_state(joint_contact_query_prepare(failed), (0.,) * 3, (0.,) * 3, 1 / 120)
    assert caught.value is failure


def test_real_rail_uses_native_mechanics_keeps_world_lock_and_recovers(monkeypatch):
    sim = Simulation(seed=0, track='coastal', traffic_count=0, config=DrivingMode.GAME.vehicle_config,
                     input_config=DrivingMode.GAME.input_config)
    original = tire_drivetrain.joint_solve
    requests = []

    def capture(*args):
        assert joint_contact_queries_world(args[3])
        requests.append(args)
        return original(*args)

    class WorldLock:
        def release(self):
            raise AssertionError('真实世界查询期间不可交出推进锁')

        def acquire(self):
            raise AssertionError('未释放的锁不应重复取得')

    solve = tire_drivetrain.DrivetrainInput.solve

    def locked(request, **kwargs):
        return solve(request, query_lock=WorldLock())

    monkeypatch.setattr(tire_drivetrain, 'joint_solve', capture)
    monkeypatch.setattr(tire_drivetrain.DrivetrainInput, 'solve', locked)
    try:
        sim.step(Control())
        assert requests
        args = requests[-1]
        expected = original(*args)
        failure = ValueError('迭代中的原始查询异常')

        def failed(*values):
            raise failure

        invalid = joint_contact_query_prepare(failed)
        with pytest.raises(ValueError) as caught:
            original(*args[:3], invalid, args[4])
        assert caught.value is failure
        assert original(*args) == expected
        # 查询可再次调用两个原生模块；原参数错误不能变成未设置异常的SystemError。
        def mechanical_failure(*values):
            dot((None,), (1.,))

        def geometry_failure(*values):
            _joint_coordinates((), (0., 0., 0.))

        for query, error in ((mechanical_failure, TypeError), (geometry_failure, ValueError)):
            with pytest.raises(error):
                original(*args[:3], joint_contact_query_prepare(query), args[4])
            assert original(*args) == expected
    finally:
        sim.close()
