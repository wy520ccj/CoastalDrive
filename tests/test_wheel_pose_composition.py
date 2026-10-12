"""轮姿只改变等价旋转的装配，位置和完整机械状态仍来自权威物理。"""

import math
import random
from dataclasses import replace

from panda3d.core import Mat3, Quat, TransformState, Vec3

from simulation import Control, Simulation


def reference_orientation(body, steering, rotation):
    steer, roll = Quat(), Quat()
    steer.setHpr(Vec3(-steering, 0, 0))
    roll.setFromAxisAngle(-math.degrees(rotation), Vec3(1, 0, 0))
    rows = [body.xform(steer.xform(roll.xform(axis)))
            for axis in (Vec3(1, 0, 0), Vec3(0, 1, 0), Vec3(0, 0, 1))]
    expected = Quat()
    expected.setFromMatrix(Mat3(*(value for row in rows for value in row)))
    return expected


def test_equivalent_wheel_orientation_keeps_all_axes_and_exact_positions():
    sim = Simulation(track='test', traffic_count=0)
    rng = random.Random(5801)
    try:
        car = sim.player
        for _ in range(1024):
            pose = TransformState.makeHpr(Vec3(rng.uniform(-180, 180), rng.uniform(-45, 45), rng.uniform(-45, 45)))
            car._chassis.setTransform(pose)
            car.tires.rotation = [rng.uniform(-1000, 1000) for _ in range(4)]
            car.tires.states = tuple(replace(state, steering=rng.uniform(-40, 40)) for state in car.tires.states)
            positions = ((1., 2., 3.),)*4
            wheels = car.tires.wheel_poses(car._chassis, car._vehicle, positions=positions)
            for wheel, state, angle in zip(wheels, car.tires.states, car.tires.rotation):
                expected = reference_orientation(pose.getQuat(), state.steering, angle)
                actual = Quat(*wheel.orientation)
                assert wheel.position == positions[0]
                for axis in (Vec3(1,0,0), Vec3(0,1,0), Vec3(0,0,1)):
                    assert (expected.xform(axis)-actual.xform(axis)).length()<2e-6
        car.reset((0., 0., .55))
        for _ in range(120):
            sim.step(Control(throttle=.2, steering=.1))
        before = tuple(car.tires.states), tuple(car.tires.rotation), car.suspension.state
        snapshot = car.snapshot()
        assert before == (tuple(car.tires.states), tuple(car.tires.rotation), car.suspension.state)
        assert tuple(w.position for w in snapshot.wheels) == car.suspension.wheel_positions(car._chassis, car._vehicle.getWheels())
    finally:
        sim.close()
