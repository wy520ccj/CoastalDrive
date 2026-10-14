"""平面研究工况和几何追踪驾驶员；只生成真实执行器输入。"""

import math

from vehicle_state import VehicleCommand


def bump_geometry(options, origin, config):
    """真实实体和视窗标记共用几何，左轮轨迹上固定矩形凸起。"""
    half = (.24, options.bump_length_m/2, options.bump_height_m/2)
    center = (origin[0]-config.wheel_track_widths[0]/2,
              origin[1]+options.bump_distance_m+half[1], half[2])
    return center, half


def lane_offset(distance):
    """3.5m参考双移线：20m入段、30m横移、20m保持、30m回线。"""
    if distance < 20:
        return 0.
    if distance < 50:
        fraction = (distance-20)/30
        return 3.5*fraction*fraction*(3-2*fraction)
    if distance < 70:
        return 3.5
    if distance < 100:
        fraction = (distance-70)/30
        return 3.5*(1-fraction*fraction*(3-2*fraction))
    return 0.


def target_point(options, state, initial):
    x, y, _ = state.position
    x0, y0, _ = initial.position
    preview = max(6., abs(state.speed)*1.2)
    if options.maneuver == "constant_radius":
        center_x, center_y = x0+options.radius_m, y0
        phase = math.atan2(y-center_y, center_x-x)+preview/options.radius_m
        return center_x-options.radius_m*math.cos(phase), center_y+options.radius_m*math.sin(phase)
    return x0+lane_offset(y-y0+preview), y+preview


def path_command(options, state, initial, config, speed_integral=0.):
    target_x, target_y = target_point(options, state, initial)
    dx, dy = target_x-state.position[0], target_y-state.position[1]
    angle = math.radians(state.heading)
    lateral = dx*math.cos(angle)+dy*math.sin(angle)
    curvature = 2*lateral/(dx*dx+dy*dy)
    steering = math.degrees(math.atan(config.wheelbase*curvature))
    steering = max(-config.steering_degrees, min(config.steering_degrees, steering))
    error = options.speed_kph/3.6-state.speed
    throttle = max(0., min(1., .12+.20*error+speed_integral))
    brake = max(0., min(1., -.12*error)) if error < -1. else 0.
    return VehicleCommand(steering=steering, throttle=throttle, brake=brake, direction=1)


def path_error(options, state, initial):
    x, y, _ = state.position
    x0, y0, _ = initial.position
    if options.maneuver == "constant_radius":
        return math.hypot(x-x0-options.radius_m, y-y0)-options.radius_m
    if options.maneuver == "double_lane_change":
        return x-x0-lane_offset(y-y0)
    return None


def reference_path(options, initial):
    x0, y0, _ = initial.position
    if options.maneuver == "constant_radius":
        radius = options.radius_m
        return tuple((x0+radius-radius*math.cos(index*2*math.pi/180),
                      y0+radius*math.sin(index*2*math.pi/180)) for index in range(181))
    if options.maneuver == "double_lane_change":
        return tuple((x0+lane_offset(distance), y0+distance) for distance in range(181))
    return ()
