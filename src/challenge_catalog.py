"""预算道路挑战目录与正式联合奖牌线。"""

from dataclasses import replace

from career import EVENTS
from challenge_rules import MEDALS, ChallengeSpec, MedalTarget
from driving_modes import DrivingMode
from overtake_routes import OVERTAKE_ROUTES
from race import GameMode
from sprint_routes import SPRINT_ROUTES, VALLEY_BRAKING_VERSION, sprint_route
from streamed_road import ROAD_EDGE_ADJUSTMENT_AVAILABLE
from tracks import COASTAL_CIRCUIT
from vehicle_designs import GAME_DESIGN

DRIVING_BASE = DrivingMode.GAME.configured_vehicle(base_config=GAME_DESIGN)
_RIDGE_SHAPE, _RIDGE_VERSION = (('budget-ridge-long-waves', 'budget-route-v5') if ROAD_EDGE_ADJUSTMENT_AVAILABLE
                               else ('budget-ridge-suspension', 'budget-route-v4'))
SPRINT_ROAD_SHAPES = {GameMode.BEND_SPRINT: 'budget-bend',
                     GameMode.RIDGE_SPRINT: _RIDGE_SHAPE,
                     GameMode.VALLEY_PACE: 'budget-valley'}


def _medals(copper, silver, gold):
    return tuple(MedalTarget(name, *pair) for name, pair in zip(MEDALS, (copper, silver, gold), strict=True))


# 铜、银、金的同次用时/油耗上限。样本及复算见 CHALLENGE-REBUILD-01/agent-calibration。
_ROAD_MEDALS = {
    'first-drive': _medals((60., 36.1), (24.9, 20.1), (22.2, 17.9)),
    'coast-sprint': _medals((80.3, 28.4), (69.2, 24.5), (61.7, 21.8)),
    'ridge-run': _medals((84.9, 28.3), (73.2, 24.4), (65.3, 21.7)),
    'coastal-cup': _medals((149.7, 25.7), (129., 22.1), (115.1, 19.7)),
    GameMode.BEND_SPRINT: _medals((124.3, 26.2), (107.1, 22.6), (95.6, 20.1)),
    GameMode.RIDGE_SPRINT: (_medals((97.5, 31.8), (84., 27.4), (75., 24.4)) if ROAD_EDGE_ADJUSTMENT_AVAILABLE
                          else _medals((96.9, 27.3), (83.5, 23.6), (74.5, 21.))),
    GameMode.VALLEY_PACE: _medals((81.6, 26.8), (70.3, 23.1), (62.7, 20.6)),
    GameMode.SAFE_OVERTAKE: _medals((113.1, 14.9), (97.5, 12.8), (87., 11.4)),
    GameMode.HILL_TRAFFIC: _medals((124.2, 15.3), (107., 13.2), (95.5, 11.7)),
    GameMode.TIME_TRIAL: _medals((74., 28.4), (63.8, 24.5), (56.9, 21.8)),
}
_MEDAL_VERSION = 'budget-energy-medals-v1'
SPRINT_CHALLENGES = {
    mode: ChallengeSpec(mode.value, route.name, DRIVING_BASE, route.gates[-1], 5000,
        version=('budget-bend-medals-v1' if mode == GameMode.BEND_SPRINT else
                 _RIDGE_VERSION+'-medals-v1' if mode == GameMode.RIDGE_SPRINT else VALLEY_BRAKING_VERSION),
        road_shape=SPRINT_ROAD_SHAPES.get(mode, ''),
        targets=_ROAD_MEDALS[mode])
    for mode, route in SPRINT_ROUTES.items()
}
CAREER_CHALLENGES = {
    event.id: ChallengeSpec(event.id, event.name, DRIVING_BASE, event.distance,
                           1500 if event.chapter == 0 else 6500 if event.chapter == 2 else 5000,
                           version=_MEDAL_VERSION, targets=_ROAD_MEDALS[event.id])
    for event in EVENTS if event.kind == 'sprint'
}
for _event in EVENTS:
    if _event.kind == 'parking':
        CAREER_CHALLENGES[_event.id] = ChallengeSpec(_event.id, _event.name, DRIVING_BASE,
            _event.distance, 1500, allowed=('brakes', 'brake_share', 'final_drive'),
            assessment='lower', metric_label='停车误差', metric_unit='m', metric_limits=(20., 10., 3.))
    elif _event.kind == 'slalom':
        CAREER_CHALLENGES[_event.id] = ChallengeSpec(_event.id, _event.name, DRIVING_BASE,
            _event.distance, 2500, allowed=('front_tire', 'rear_tire', 'springs', 'dampers', 'antiroll_share'),
            assessment='career-slalom', metric_label='通过道路门', metric_unit='门', metric_limits=(_event.gold,))
SPECIALIST_CHALLENGES = {
    GameMode.BRAKING_LESSON: ChallengeSpec('braking_lesson', '定点刹停', DRIVING_BASE, 170., 1500,
        allowed=('brakes', 'brake_share', 'final_drive'), assessment='lower',
        metric_label='停车误差', metric_unit='m', metric_limits=(10., 5., 2.)),
    GameMode.SHORT_BRAKING: ChallengeSpec('short_braking', '短距制动验车', DRIVING_BASE, 142., 2500,
        allowed=('brakes', 'brake_share', 'mass'), assessment='lower',
        metric_label='停车距离', metric_unit='m', metric_limits=(42., 36., 33.)),
    GameMode.SLALOM_LESSON: ChallengeSpec('slalom_lesson', '连续过门', DRIVING_BASE, 320., 2500,
        allowed=('front_tire', 'rear_tire', 'springs', 'dampers', 'antiroll_share'), assessment='lower',
        metric_label='过门用时', metric_unit='s', metric_limits=(24., 18., 15.)),
    GameMode.FAST_SLALOM: ChallengeSpec('fast_slalom', '高速验车', DRIVING_BASE, 320., 5000,
        allowed=('front_tire', 'rear_tire', 'springs', 'dampers', 'antiroll_share'), assessment='lower',
        metric_label='过门用时', metric_unit='s', metric_limits=(14., 12.5, 11.5)),
}
OVERTAKE_CHALLENGES = {
    mode: ChallengeSpec(mode.value, route.title, DRIVING_BASE, route.distance, 5000,
                        version='budget-overtake-finish-v1', targets=_ROAD_MEDALS[mode])
    for mode, route in OVERTAKE_ROUTES.items()
}
ROAD_CHALLENGES = {**SPRINT_CHALLENGES, **CAREER_CHALLENGES, **SPECIALIST_CHALLENGES, **OVERTAKE_CHALLENGES,
    GameMode.TIME_TRIAL: ChallengeSpec('time_trial', '滨海计时', DRIVING_BASE, COASTAL_CIRCUIT.length, 5000,
                                      version=_MEDAL_VERSION, targets=_ROAD_MEDALS[GameMode.TIME_TRIAL]),
    GameMode.DISTANCE_CHALLENGE: ChallengeSpec('distance_challenge', '5公里无碰撞挑战',
                                              DRIVING_BASE, 5000., 6500, version='budget-distance-lanes-v1')}

# 五公里的固定种子0。各路况的原始记录见 CHALLENGE-REBUILD-01/distance-medals。
_DISTANCE_MEDALS = {
    ('straight', 'light'): _medals((214.2, 15.3), (184.5, 13.2), (164.7, 11.7)),
    ('straight', 'normal'): _medals((253.3, 14.1), (218.2, 12.1), (194.8, 10.8)),
    ('straight', 'busy'): _medals((285.4, 13.3), (245.9, 11.5), (219.5, 10.2)),
    ('hills', 'light'): _medals((235.9, 14.5), (203.2, 12.5), (181.4, 11.1)),
    ('hills', 'normal'): _medals((271.7, 12.4), (234.1, 10.7), (209., 9.5)),
    ('hills', 'busy'): _medals((297.2, 12.1), (256.1, 10.5), (228.6, 9.3)),
}


def distance_challenge_spec(shape, density, seed=0):
    spec = ROAD_CHALLENGES[GameMode.DISTANCE_CHALLENGE]
    targets = _DISTANCE_MEDALS.get((shape, density)) if seed == 0 else None
    return replace(spec, version='budget-distance-medals-v2', targets=targets) if targets else spec


def course_key(mode, event_id=None):
    return event_id if mode == GameMode.CAREER else mode


def course_mode(key):
    return GameMode.CAREER if isinstance(key, str) else key


def course_gates(key):
    if key == GameMode.TIME_TRIAL:
        return (*COASTAL_CIRCUIT.checkpoints, COASTAL_CIRCUIT.length)
    if key in SPRINT_ROUTES:
        return sprint_route(key, ROAD_CHALLENGES[key].version).gates
    distance = ROAD_CHALLENGES[key].distance_m
    return tuple(distance*i/4 for i in range(1, 5))


def course_shape(key):
    if ROAD_CHALLENGES[key].road_shape:
        return ROAD_CHALLENGES[key].road_shape
    if key in SPRINT_ROUTES:
        return SPRINT_ROUTES[key].shape
    if key in OVERTAKE_ROUTES:
        return OVERTAKE_ROUTES[key].shape
    if isinstance(key, str):
        return next(event.shape for event in EVENTS if event.id == key)
    return 'straight'


def course_track(key):
    return 'coastal' if key == GameMode.TIME_TRIAL else 'endless'
