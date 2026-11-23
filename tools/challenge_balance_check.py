"""同一道路策略实跑预算方案；不冒充真人样本，不授奖，不改生产阈值。"""

import argparse
import hashlib
import json
import math
import os
import sys
from dataclasses import asdict, replace
from pathlib import Path
from time import perf_counter

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'src'))

from career_courses import COURSES
from challenge_build import BuildDraft
from challenge_catalog import ROAD_CHALLENGES, course_mode, course_shape, course_track
from highway_run import TRAFFIC_DENSITIES
from overtake_routes import OVERTAKE_ROUTES
from race import BestTimes, GameMode
from road_test_driver import OvertakeDriver, pursuit_control, valley_braking_policy
from session import Phase, Session
from sprint_routes import SPRINT_ROUTES, sprint_route
from vehicle_state import Control

ROUTE_KEYS = {key.value if isinstance(key, GameMode) else key: key
              for key, spec in ROAD_CHALLENGES.items() if spec.assessment == 'road'}
ROUGH_RANGES = {'budget-ridge-rough': (530., 650.), 'budget-ridge-suspension': (530., 770.),
                'budget-ridge-long-waves': (530., 770.)}
DRIVER_SOURCE = ROOT/'src/road_test_driver.py'

BUILDS = {
    'stock': BuildDraft(),
    'free-setup': BuildDraft(brake_share=.65, antiroll_share=.4),
    'power-only': BuildDraft(power=1.15),
    'final-only': BuildDraft(final_drive=1.075),
    'mass-only': BuildDraft(mass=.96),
    'drag-only': BuildDraft(drag=.95),
    'front-tire115': BuildDraft(front_tire=1.15),
    'front-tire130': BuildDraft(front_tire=1.3),
    'power': BuildDraft(power=1.15, final_drive=1.075),
    'handling': BuildDraft(front_tire=1.15, rear_tire=1.15, springs=1.125, dampers=1.125),
    'turn-in': BuildDraft(front_tire=1.3, rear_tire=.8, antiroll_share=.15),
    'braking': BuildDraft(brakes=1.25, brake_share=.65),
    'brakes-only': BuildDraft(brakes=1.25),
    'springs-soft': BuildDraft(springs=.75),
    'springs-firm': BuildDraft(springs=1.25),
    'dampers-soft': BuildDraft(dampers=.75),
    'dampers-firm': BuildDraft(dampers=1.25),
    'rough-front': BuildDraft(front_tire=1.3),
    'rough-free': BuildDraft(front_tire=1.3, brake_share=.65, antiroll_share=.4),
    'rough-firm-damped': BuildDraft(front_tire=1.3, springs=1.25, dampers=1.25,
                                    brake_share=.65, antiroll_share=.4),
    'rough-soft': BuildDraft(front_tire=1.3, springs=.75),
    'rough-free-soft': BuildDraft(front_tire=1.3, springs=.75, brake_share=.65, antiroll_share=.4),
    'rough-damped': BuildDraft(front_tire=1.3, dampers=1.25),
    'rough-balanced': BuildDraft(front_tire=1.3, springs=.875, dampers=1.125),
    'efficiency': BuildDraft(mass=.96, drag=.95),
    'balanced': BuildDraft(power=1.10, front_tire=1.15, rear_tire=1.15,
                          springs=1.125, final_drive=1.075),
}
for _name in ('power-only', 'braking', 'efficiency', 'balanced', 'front-tire130'):
    BUILDS['tuned-'+_name] = replace(BUILDS[_name], brake_share=.65, antiroll_share=.4)


class RoadPilot:
    def __init__(self, simulation, mode, *, target_kph=75., curve_acceleration=2.5,
                 braking_acceleration=2.5, rough_acceleration=None, rough_target_kph=None,
                 steering_reserve=None, sprint_version=''):
        self.simulation, self.mode = simulation, mode
        self.origin = (simulation.road.locate(simulation.snapshot().player)[0]
                       +(0. if simulation.road.curve else simulation.origin_y))
        self.policy = {'id': 'road-budget-pursuit-v3', 'target_kph': target_kph,
                       'preview_seconds': .65, 'curve_acceleration': curve_acceleration,
                       'braking_acceleration': braking_acceleration,
                       'decision_hz': 20, 'physics_hz': 120}
        self.last = Control()
        if steering_reserve is not None and not 0 < steering_reserve < 1:
            raise ValueError('转向余量目标须在0至1之间')
        self.observations = []
        self.dynamics = []
        self.traffic_driver = None
        if mode in (*OVERTAKE_ROUTES, GameMode.DISTANCE_CHALLENGE):
            self.traffic_driver = OvertakeDriver(simulation.road, simulation.config,
                                                simulation.input_config, target_kph/3.6)
            self.policy = {'id': 'road-budget-traffic-v1', 'target_kph': target_kph,
                           'decision_hz': 20, 'control_hz': 120, 'physics_hz': 120,
                           'driver_sha256': hashlib.sha256(DRIVER_SOURCE.read_bytes()).hexdigest()}
        if rough_acceleration is not None:
            self.policy.update(id='road-budget-pursuit-v5', rough_curve_acceleration=rough_acceleration,
                               rough_range_m=ROUGH_RANGES[simulation.road_shape])
        if rough_target_kph is not None:
            start, end = ROUGH_RANGES[simulation.road_shape]
            self.policy.update(id='road-budget-pursuit-v5', rough_target_kph=rough_target_kph,
                               rough_target_range_m=(start-60., end))
        if steering_reserve is not None:
            if self.traffic_driver is not None:
                raise ValueError('转向余量策略只用于无交通道路比较')
            self.policy.update(id='road-budget-pursuit-v6', steering_reserve=steering_reserve)
        route = sprint_route(mode, sprint_version) if mode in SPRINT_ROUTES else None
        self.speed_zone = None if route is None else route.speed_zone
        self.policy.update(valley_braking_policy(route))
        if 'entry_lock_m' in self.policy:
            self.policy.update(id='road-budget-valley-braking-v1', decision_hz=120)
        if self.speed_zone is not None:
            self.policy['speed_zone'] = asdict(self.speed_zone)
            self.policy['zone_target_kph'] = (self.speed_zone.minimum_kph+self.speed_zone.maximum_kph)/2

    def sample(self, state, dt):
        if self.traffic_driver is not None:
            self.last = self.traffic_driver.sample(state, dt)
        elif 'entry_lock_m' in self.policy or state.tick % 6 == 0:
            self.last = self.road_control(state)
        if state.tick % 6 == 0:
            self.observe(state)
        return self.last

    def road_control(self, state):
        return pursuit_control(self.simulation, state, self.origin, self.policy, self.speed_zone)

    def observe(self, state):
        car, config = state.player, self.simulation.config
        distance, lateral = self.simulation.road.locate(car)
        progress = distance+(0. if self.simulation.road.curve else state.origin_y)-self.origin
        self.observations.append((state.tick, progress, lateral, car.speed*3.6,
            car.position[0], car.position[1]+state.origin_y, car.position[2], self.last.steering))
        grade = math.radians(self.simulation.road.sample_lateral(distance, 0.).grade)
        vertical_error = car.velocity[2]-math.hypot(*car.velocity[:2])*math.tan(grade)
        loads = car.suspension_state.normal_force
        self.dynamics.append((state.tick, progress, vertical_error, car.pitch, car.roll,
            *loads, sum(loads)/(config.mass*9.81), sum(wheel.road_support for wheel in car.wheel_dynamics),
            sum(brake.abs_active for brake in car.brake_states)))


def ride_summary(samples):
    return {'samples': len(samples), 'vertical_rms_mps': math.sqrt(sum(row[2]**2 for row in samples)/len(samples)),
            'pitch_span_deg': max(row[3] for row in samples)-min(row[3] for row in samples),
            'load_factor_min': min(row[9] for row in samples), 'load_factor_max': max(row[9] for row in samples),
            'support_loss_samples': sum(row[10] < 4 for row in samples),
            'abs_active_samples': sum(row[11] > 0 for row in samples)}


def run(output, routes, builds, seconds, target_kph, curve_acceleration, braking_acceleration=2.5,
        ridge_profile=None, rough_acceleration=None, rough_target_kph=None, steering_reserve=None, *,
        distance_shape=None, distance_density=None):
    tool_hash = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    controller_hash = hashlib.sha256(DRIVER_SOURCE.read_bytes()).hexdigest()
    if (distance_shape is not None or distance_density is not None) and routes != ['distance_challenge']:
        raise ValueError('道路和密度选项仅用于单独的5公里无碰撞挑战')
    # 路线设计试验仅在本进程加载；完整规格哈希进入独立规则及原始记录，不改默认目录。
    profile_bytes = None if ridge_profile is None else ridge_profile.read_bytes()
    profile_hash = None
    if profile_bytes is not None:
        profile = json.loads(profile_bytes)
        if profile['course_id'] not in ROUGH_RANGES or routes != ['ridge_sprint']:
            raise ValueError('起伏设计试验只允许单独山脊候选')
        profile_hash = hashlib.sha256(profile_bytes).hexdigest()
        spec = ROAD_CHALLENGES[GameMode.RIDGE_SPRINT]
        if profile['distance_m'] != spec.distance_m or sum(row[0] for row in profile['sections']) != spec.distance_m:
            raise ValueError('设计路线长度与本关不一致')
        COURSES[profile['course_id']] = tuple(tuple(row) for row in profile['sections'])
        ROAD_CHALLENGES[GameMode.RIDGE_SPRINT] = replace(spec, road_shape=profile['course_id'],
            version='budget-ridge-design-'+profile_hash[:16])
    if (rough_acceleration is not None or rough_target_kph is not None) and (routes != ['ridge_sprint']
            or ROAD_CHALLENGES[GameMode.RIDGE_SPRINT].road_shape not in ROUGH_RANGES):
        raise ValueError('局部策略只用于有明确起伏区间的山脊路线')
    # 先核对整批候选，避免跑到中途才发现某方案超出本关预算。
    for route_id in routes:
        spec = ROAD_CHALLENGES[ROUTE_KEYS[route_id]]
        for name in builds:
            spec.configuration(BUILDS[name])
            if BUILDS[name].cost > spec.budget:
                raise ValueError(f'{route_id}/{name}超预算，不能混入本批预算内比较')
    output.mkdir(parents=True, exist_ok=False)
    if profile_bytes is not None:
        (output/'ridge-design-profile.json').write_bytes(profile_bytes)
    os.environ['LOCALAPPDATA'] = str(output/'user')
    rows = []
    for route_id in routes:
        key = ROUTE_KEYS[route_id]
        spec, mode = ROAD_CHALLENGES[key], course_mode(key)
        for name in builds:
            build = BUILDS[name]
            folder = output/(route_id+'-'+name)
            folder.mkdir()
            session = Session(track='test', scores=BestTimes(folder/'best.json'))
            try:
                session.road_shape = distance_shape or course_shape(key)
                if distance_density is not None:
                    session.traffic_density = distance_density
                session.start(mode=mode, track=course_track(key), countdown=False, settle_initial=True,
                              challenge_spec=spec, build=build,
                              career_event_id=key if mode == GameMode.CAREER else None)
                initial_collisions = session.current.collisions
                pilot = RoadPilot(session.simulation, mode, target_kph=target_kph,
                                  curve_acceleration=curve_acceleration, braking_acceleration=braking_acceleration,
                                  rough_acceleration=rough_acceleration, rough_target_kph=rough_target_kph,
                                  steering_reserve=steering_reserve, sprint_version=spec.version)
                session.set_controller(pilot)
                started = perf_counter()
                for _ in range(round(seconds*120)):
                    before = session.current
                    try:
                        session.tick()
                    except ArithmeticError as error:
                        (folder/'failure.json').write_text(json.dumps({'route': route_id, 'build_name': name,
                            'build': asdict(build), 'policy': pilot.policy, 'error': str(error),
                            'last_valid_snapshot': asdict(before), 'attempted_control': asdict(session.last_control),
                            'path_samples': pilot.observations, 'dynamics_samples': pilot.dynamics},
                            ensure_ascii=False, allow_nan=False)+'\n', encoding='utf-8')
                        raise
                    if session.phase == Phase.RESULTS:
                        break
                if session.phase != Phase.RESULTS:
                    session.finish()
                state = session.highway.snapshot.engineering
                trace_path = Path(state.trace_path)
                trace_bytes = trace_path.read_bytes()
                trace = json.loads(trace_bytes)
                source_stable = trace['source_start'] == trace['source_end']
                row = {'route': route_id, 'build_name': name, 'build': asdict(build),
                       'track': session.simulation.track, 'shape': session.road_shape,
                       'design_profile_sha256': profile_hash,
                       'policy': pilot.policy, 'wall_seconds': perf_counter()-started,
                       'status': asdict(state), 'physical_ticks': session.current.tick,
                       'collisions': session.current.collisions-initial_collisions,
                       'traffic_result': (None if session.highway.snapshot.overtake is None else
                                          asdict(session.highway.snapshot.overtake)),
                       'source_stable': source_stable, 'source': trace['source_start'],
                       'trace_sha256': hashlib.sha256(trace_bytes).hexdigest(),
                       'path_max_m': max(abs(sample[2]) for sample in pilot.observations),
                       'path_rms_m': math.sqrt(sum(sample[2]**2 for sample in pilot.observations)/len(pilot.observations))}
                row['ride'] = {'whole': ride_summary(pilot.dynamics)}
                rough_range = ROUGH_RANGES.get(spec.road_shape, (530., 650.) if spec.road_shape == 'budget-ridge' else None)
                if rough_range:
                    start, end = rough_range
                    undulations = [sample for sample in pilot.dynamics if start <= sample[1] <= end]
                    if undulations:
                        row['ride']['undulations'] = ride_summary(undulations)
                (folder/'dynamics.json').write_text(json.dumps({'sample_hz': 20,
                    'columns': ('tick', 'progress_m', 'vertical_tracking_mps', 'pitch_deg', 'roll_deg',
                                'normal_fl_n', 'normal_fr_n', 'normal_rl_n', 'normal_rr_n',
                                'total_load_over_mg', 'supported_wheels', 'abs_active_wheels'),
                    'samples': pilot.dynamics}, ensure_ascii=False)+'\n', encoding='utf-8')
                (folder/'path.json').write_text(json.dumps({'sample_hz': 20,
                    'columns': ('tick', 'progress_m', 'lateral_m', 'kph', 'x', 'global_y', 'z', 'steering'),
                    'samples': pilot.observations}, ensure_ascii=False)+'\n', encoding='utf-8')
                rows.append(row)
                (output/'summary.json').write_text(json.dumps({'rows': rows, 'completed': len(rows) == len(routes)*len(builds),
                    'tool_sha256': tool_hash, 'controller_sha256': controller_hash,
                    'scope': '真实道路与Control自动驾驶；不是真人/驾驶FPS/金牌标定样本。'},
                    ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
                print(json.dumps({'route': route_id, 'build': name, 'valid': state.result.valid,
                                  'seconds': state.seconds, 'oil': state.consumption,
                                  'reason': state.result.notice}), flush=True)
                if (not source_stable or hashlib.sha256(Path(__file__).read_bytes()).hexdigest() != tool_hash
                        or hashlib.sha256(DRIVER_SOURCE.read_bytes()).hexdigest() != controller_hash):
                    raise ValueError('试车期间源码或SDK改变，停止本批，已有输出保留为探索证据')
            finally:
                session.close()


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--routes', nargs='+', choices=tuple(ROUTE_KEYS),
                        default=['bend_sprint', 'ridge_sprint', 'valley_pace'])
    parser.add_argument('--builds', nargs='+', choices=tuple(BUILDS), default=list(BUILDS))
    parser.add_argument('--seconds', type=float, default=180.)
    parser.add_argument('--target-kph', type=float, default=75.)
    parser.add_argument('--curve-acceleration', type=float, default=2.5)
    parser.add_argument('--braking-acceleration', type=float, default=2.5)
    parser.add_argument('--ridge-profile', type=Path, help='仅本进程加载已保存的候选米制设计，独立成绩分组')
    parser.add_argument('--rough-acceleration', type=float, help='仅调整山脊实际起伏段预瞄弯速，其余策略保持')
    parser.add_argument('--rough-target-kph', type=float, help='仅调整起伏段及其前60米加速目标，区外保持')
    parser.add_argument('--steering-reserve', type=float, help='方向接近打满时减速，0至1；省略沿用原策略')
    parser.add_argument('--distance-shape', choices=('straight', 'hills'), help='仅5公里挑战使用的菜单道路')
    parser.add_argument('--distance-density', choices=tuple(TRAFFIC_DENSITIES), help='仅5公里挑战使用的菜单车流密度')
    args = parser.parse_args()
    run(args.output.resolve(), args.routes, args.builds, args.seconds, args.target_kph, args.curve_acceleration,
        args.braking_acceleration, args.ridge_profile, args.rough_acceleration, args.rough_target_kph,
        args.steering_reserve, distance_shape=args.distance_shape, distance_density=args.distance_density)
