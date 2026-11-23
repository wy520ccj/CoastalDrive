"""固定路线试车员，在权威车辆状态上计算下一拍驾驶输入。"""

import math

from braking_lesson import ENTRY_DISTANCE, STOP_SPEED
from driver_assist import steering_limit
from highway_driver import HighwayDriver
from overtake_routes import OVERTAKE_ROUTES
from race import GameMode
from short_braking import MAX_KPH, MIN_KPH
from slalom_lesson import ENTRY_DISTANCE as SLALOM_ENTRY_DISTANCE
from slalom_lesson import GATES as SLALOM_GATES
from sprint_routes import SPRINT_ROUTES, VALLEY_BRAKING_VERSION, sprint_route
from vehicle_state import Control

# 策略更新后用新分组，避免跨策略比较两套车辆。
TRIAL_POLICY_VERSION = 'road-trial-v1'
TRIAL_POLICIES = {
    'first-drive': {'target_kph': 80., 'curve_acceleration': 2.5},
    'coast-sprint': {'target_kph': 95., 'curve_acceleration': 2.5},
    'ridge-run': {'target_kph': 95., 'curve_acceleration': 2.5, 'steering_reserve': .9},
    'coastal-cup': {'target_kph': 95., 'curve_acceleration': 2.5},
    GameMode.BEND_SPRINT.value: {'target_kph': 105., 'curve_acceleration': 4.4, 'steering_reserve': .9},
    GameMode.VALLEY_PACE.value: {'target_kph': 100., 'curve_acceleration': 3.4, 'braking_acceleration': 2.8},
    GameMode.RIDGE_SPRINT.value: {'target_kph': 105., 'curve_acceleration': 3.8},
    GameMode.TIME_TRIAL.value: {'target_kph': 105., 'curve_acceleration': 3.3, 'steering_reserve': .9},
    GameMode.SAFE_OVERTAKE.value: {'target_kph': 144.},
    GameMode.HILL_TRAFFIC.value: {'target_kph': 140.},
    GameMode.DISTANCE_CHALLENGE.value: {'target_kph': 144.},
    GameMode.SHORT_BRAKING.value: {'target_kph': (MIN_KPH+MAX_KPH)/2},
    GameMode.FAST_SLALOM.value: {'target_kph': 75.5},
}


def slalom_path_lateral(distance):
    before, start = SLALOM_ENTRY_DISTANCE, 0.
    for after, end in SLALOM_GATES:
        if distance <= after:
            fraction = max(0., min(1., (distance-before)/(after-before)))
            return start+(end-start)*.5*(1-math.cos(math.pi*fraction))
        before, start = after, end
    return 0.


def valley_braking_policy(route):
    if route is None or route.version != VALLEY_BRAKING_VERSION:
        return {}
    return {'entry_lock_m': route.gates[0], 'entry_target_kph': route.entry_kph+4.}


class OvertakeDriver:
    def __init__(self, road, config, input_config, speed=40.):
        self.road = road
        self.driver = HighwayDriver(1, 41, config=config, input_config=input_config)
        self.driver.cruise = self.driver.preferred_speed = self.driver.target_speed = speed
        # 固定试车员的速度意图，正常交通仍按各自风格运行。
        self.driver.speed_clock = 1e9
        self.steps = 0

    def sample(self, state, dt):
        car, traffic = state.player, state.traffic
        if self.steps % 6 == 0:
            self.driver.plan(car, traffic, self.road, [])
        self.steps += 1
        return self.driver.control(car, traffic, self.road,
                                   [self.road.locate(item) for item in (car, *traffic)])


class RoadTestDriver:
    def __init__(self, mode, challenge_id, road_shape, *, sprint_version=''):
        self.mode = mode
        self.policy = {'braking_acceleration': 2.5, **TRIAL_POLICIES[challenge_id]}
        if mode == GameMode.RIDGE_SPRINT and road_shape == 'budget-ridge-long-waves':
            self.policy.update(target_kph=102., rough_curve_acceleration=6.5, rough_range_m=(530., 770.),
                               rough_target_kph=125., rough_target_range_m=(470., 770.), steering_reserve=.9)
        if mode == GameMode.DISTANCE_CHALLENGE and road_shape == 'hills':
            self.policy['target_kph'] = 128.
        route = sprint_route(mode, sprint_version) if mode in SPRINT_ROUTES else None
        self.zone = None if route is None else route.speed_zone
        self.policy.update(valley_braking_policy(route))
        self.traffic_driver = None
        self.origin = None
        self.last = Control()

    def bind(self, simulation):
        self.simulation = simulation
        if self.mode in OVERTAKE_ROUTES or self.mode == GameMode.DISTANCE_CHALLENGE:
            self.traffic_driver = OvertakeDriver(simulation.road, simulation.config, simulation.input_config,
                                                self.policy['target_kph']/3.6)

    def sample(self, state, dt):
        if self.traffic_driver is not None:
            return self.traffic_driver.sample(state, dt)
        if self.origin is None:
            road = self.simulation.road
            self.origin = road.locate(state.player)[0]+(0. if road.curve else state.origin_y)
        if self.mode == GameMode.SHORT_BRAKING:
            speed = state.player.velocity[1]
            if state.player.position[1]+state.origin_y-self.origin >= ENTRY_DISTANCE:
                # 过门全制动，停稳前渐松踏板，给踏板平滑与轮胎卸力留出时间。
                return Control(brake=max(0., min(1., (speed-STOP_SPEED)/1.35)))
            delta = self.policy['target_kph']/3.6-speed
            return Control(throttle=max(0., min(1., .5+2*delta)))
        if self.mode == GameMode.FAST_SLALOM:
            return self._slalom_control(state)
        if 'entry_lock_m' in self.policy or state.tick % 6 == 0:
            self.last = pursuit_control(self.simulation, state, self.origin, self.policy, self.zone)
        return self.last

    def _slalom_control(self, state):
        car, config = state.player, self.simulation.config
        speed = car.velocity[1]
        x, y = car.position[:2]
        position = y+state.origin_y-self.origin
        preview = position+max(0., speed)*.22
        # 走门内侧给转向留余量，预先跟随曲率，再按真实横向位置和速度纠偏。
        inside = .78
        target_x = inside*slalom_path_lateral(position)
        slope = inside*(slalom_path_lateral(position+1.)-slalom_path_lateral(position-1.))*.5
        curvature = inside*(slalom_path_lateral(preview+1.)-2*slalom_path_lateral(preview)
                            +slalom_path_lateral(preview-1.))
        travel_slope = car.velocity[0]/max(4., speed)
        correction = .01*(target_x-x)+.18*(slope-travel_slope)
        wheel = math.degrees(math.atan(config.wheelbase*(curvature+correction)))
        limit = steering_limit(speed, config, self.simulation.input_config)
        delta = self.policy['target_kph']/3.6-speed
        return Control(steering=max(-1., min(1., wheel/limit)),
                       throttle=max(0., min(1., .18+.4*delta)),
                       brake=max(0., min(1., -.3*delta)) if delta < -.5 else 0.)


def pursuit_control(simulation, state, origin, policy, zone):
    car, road, config = state.player, simulation.road, simulation.config
    distance, _ = road.locate(car)
    speed = abs(car.speed)
    look = max(7., speed*.65)
    point = road.sample_lateral(distance+look, 0.)
    dx, dy = point.x-car.position[0], point.y-car.position[1]
    error = (math.atan2(-dx, dy)-math.radians(car.heading)+math.pi)%(2*math.pi)-math.pi
    wheel = math.degrees(math.atan2(2*config.wheelbase*math.sin(error), math.hypot(dx, dy)))
    requested = -wheel/steering_limit(speed, config, simulation.input_config)
    steering = max(-1., min(1., requested))
    target = policy['target_kph']/3.6
    relative = distance+(0. if road.curve else state.origin_y)-origin
    if ('rough_target_kph' in policy
            and policy['rough_target_range_m'][0] <= relative <= policy['rough_target_range_m'][1]):
        target = policy['rough_target_kph']/3.6
    braking = policy['braking_acceleration']
    entry_lock = policy.get('entry_lock_m')
    # 根据真实弯曲率和限速带提前制动，不读取奖牌门槛。
    for ahead in (10., 25., 45., 70.):
        if entry_lock is not None and relative < zone.start <= relative+ahead:
            continue
        a, b = road.sample_lateral(distance+ahead, 0.), road.sample_lateral(distance+ahead+5, 0.)
        curve = abs(math.radians((b.heading-a.heading+180)%360-180))/5
        acceleration = policy['curve_acceleration']
        if ('rough_curve_acceleration' in policy
                and policy['rough_range_m'][0] <= relative+ahead <= policy['rough_range_m'][1]):
            acceleration = policy['rough_curve_acceleration']
        safe = math.sqrt(acceleration/max(curve, 1e-5))
        target = min(target, math.sqrt(safe*safe+2*braking*max(0., ahead-10.)))
    in_braking_window = entry_lock is not None and entry_lock <= relative < zone.start
    if entry_lock is not None and entry_lock-45. <= relative < entry_lock:
        target = min(target, policy['entry_target_kph']/3.6)
    if in_braking_window:
        target = min(target, (zone.maximum_kph-5.)/3.6)
    elif zone is not None and relative <= zone.end and (entry_lock is None or relative >= zone.start):
        safe = (zone.minimum_kph+zone.maximum_kph)/2/3.6
        remaining = max(0., zone.start-relative-10.)
        target = min(target, math.sqrt(safe*safe+2*braking*remaining))
    if 'steering_reserve' in policy and speed > 5. and abs(requested) > policy['steering_reserve']:
        target = min(target, speed*math.sqrt(policy['steering_reserve']/abs(requested)))
    delta = target-car.speed
    brake_gain = .45 if in_braking_window else .3
    return Control(steering=steering, throttle=max(0., min(1., .18+.4*delta)),
                   brake=max(0., min(1., -brake_gain*delta)) if delta < -.5 else 0.)
