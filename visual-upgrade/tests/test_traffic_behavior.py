from highway_driver import HighwayDriver, motion
from traffic import Road
from vehicle_state import CarState


def test_diagonal_intrusion_is_seen_before_lane_overlap_with_reaction_delay():
    road = Road("endless")
    driver = HighwayDriver(1, 7)
    car = CarState((0, 100, 0.42), speed=20)
    intruder = CarState((3.1, 105, 0.42), speed=18, velocity=(-2, 18, 0))
    assert driver.neighbors(car, [intruder], road, 1)[0][1] is None
    driver.anticipate(car, [intruder], road)
    assert driver.hazard_brake == 0 and driver.avoid_offset == 0
    for _ in range(14):
        driver.anticipate(car, [intruder], road)
    assert driver.hazard_brake > 0
    assert -0.65 <= driver.avoid_offset < 0
    action = driver.control(car, [intruder], road, [(100, 0), (105, 3.1)])
    assert action.brake > 0 and action.throttle == 0


def test_side_yield_does_not_swerve_into_another_car():
    road = Road("endless")
    driver = HighwayDriver(1, 7)
    car = CarState((0, 100, 0.42), speed=20)
    right = CarState((3.1, 103, 0.42), speed=18, velocity=(-2, 18, 0))
    left = CarState((-2.4, 100, 0.42), speed=20)
    for _ in range(20):
        driver.anticipate(car, [right, left], road)
    assert driver.avoid_offset == 0
    assert driver.hazard_brake > 0


def test_fast_follower_prompts_safe_yield_but_not_into_an_occupied_lane():
    road = Road("endless")
    car = CarState((0, 100, 0.42), speed=22)
    follower = CarState((0, 65, 0.42), speed=30)
    driver = HighwayDriver(1, 7)
    driver.decision_clock = 0
    for _ in range(15):
        driver.plan(car, [follower], road, [])
    assert driver.phase == "signal" and driver.target_lane == 2
    assert driver.reason == "yield_rear"
    blocked = HighwayDriver(1, 7)
    blocked.decision_clock = 0
    neighbor = CarState((4.5, 100, 0.42), speed=22)
    left = CarState((-4.5, 100, 0.42), speed=22)
    for _ in range(15):
        blocked.plan(car, [follower, neighbor, left], road, [])
    assert blocked.phase == "cruise"
    action = blocked.control(
        car, [follower, neighbor, left], road, [(100, 0), (65, 0), (100, 4.5), (100, -4.5)]
    )
    assert blocked.hazard_brake == 0
    assert action.brake == 0


def test_cruising_returns_right_after_a_clear_interval():
    road = Road("endless")
    driver = HighwayDriver(0, 42)
    car = CarState((-4.5, 100, 0.42), speed=25)
    for _ in range(160):
        driver.plan(car, [], road, [])
    assert driver.target_lane == 1
    assert driver.reason == "keep_right"


def test_pace_changes_are_visible_but_bounded_and_repeatable():
    road = Road("endless")
    a, b = HighwayDriver(1, 42), HighwayDriver(1, 42)
    car = CarState((0, 100, 0.42), speed=25)
    values = []
    for _ in range(2400):
        previous = a.cruise
        a.plan(car, [], road, [])
        b.plan(car, [], road, [])
        assert a.cruise == b.cruise
        assert abs(a.cruise - previous) <= 0.030001
        values.append(a.cruise)
    assert max(values) - min(values) > 3.5
    assert min(values) >= 17 and max(values) <= 36


def test_world_velocity_distinguishes_oncoming_and_sliding_cars():
    assert motion(CarState((0, 0, 0), heading=180, speed=20))[1] == -20
    assert motion(CarState((0, 0, 0), speed=20, velocity=(3, 17, 0))) == (3, 17)
