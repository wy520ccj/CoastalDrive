"""实验信号的单位和真实字段来源；接触未定义值保留None。"""

import math
from dataclasses import dataclass


@dataclass(frozen=True)
class Signal:
    key: str
    label: str
    unit: str
    source: str


SIGNALS = (
    Signal("time", "试验时间", "s", "Snapshot.time - initial.time"),
    Signal("tick", "物理拍", "1", "Snapshot.tick; includes initialization ticks"),
    Signal("speed", "车速", "km/h", "Snapshot.player.speed * 3.6"),
    Signal("ax", "纵向加速度", "m/s²", "Snapshot.player.acceleration"),
    Signal("ay", "横向加速度", "m/s²", "Snapshot.player.lateral_acceleration"),
    Signal("yaw", "横摆角速度", "rad/s", "Snapshot.player.dynamics.yaw_rate"),
    Signal("horizontal_speed", "水平速度模", "m/s", "hypot(Snapshot.player.velocity.x, velocity.y)"),
    Signal("beta", "车身侧偏角", "deg", "Snapshot.player.dynamics.sideslip; horizontal_speed<=1m/s undefined"),
    Signal("roll", "车身侧倾角", "deg", "Snapshot.player.roll"),
    Signal("ltr_front", "前轴左右轮荷差比", "1", "(sample_load_fr-sample_load_fl)/(sample_load_fr+sample_load_fl)"),
    Signal("ltr_rear", "后轴左右轮荷差比", "1", "(sample_load_rr-sample_load_rl)/(sample_load_rr+sample_load_rl)"),
    Signal("steering", "实际转角", "deg", "Snapshot.player.steering"),
    Signal("steering_request", "转角请求", "deg", "VehicleCommand.steering"),
    Signal("throttle", "油门踏板", "1", "Snapshot.player.throttle"),
    Signal("brake", "制动踏板", "1", "Snapshot.player.brake"),
    Signal("engine_throttle", "电子油门响应", "1", "Snapshot.player.powertrain_state.throttle"),
    Signal("throttle_request", "油门请求", "1", "VehicleCommand.throttle"),
    Signal("brake_request", "制动请求", "1", "VehicleCommand.brake"),
    Signal("gear", "实际挡位", "1", "Snapshot.player.gear"),
    Signal("rpm", "发动机转速", "rpm", "Snapshot.player.rpm"),
    Signal("clutch", "实际离合", "1", "Snapshot.player.powertrain_state.clutch_position"),
    Signal("clutch_request", "离合请求", "1", "VehicleCommand.clutch; None=automatic"),
    Signal("gear_request", "挡位请求", "1", "VehicleCommand.gear; None=automatic"),
    Signal("path_error", "路径误差", "m", "lab_maneuvers.path_error(options, Snapshot.player, initial)"),
    *(Signal(f"{field}_{wheel}", f"{label} {wheel.upper()}", unit,
             f"Snapshot.player.wheel_dynamics[{index}].{attribute}")
      for field, label, unit, attribute in (
          ("kappa", "滑移率", "1", "kappa"), ("load", "施力阶段轮荷", "N", "normal_load"),
          ("alpha", "轮胎侧偏角", "rad", "alpha"),
          ("force_grip", "施力附着预算", "N", "force_grip"),
          ("force_residual", "施力分量残差", "N", "force_residual"),
          ("force_tick", "施力接点拍", "1", "force_contact_tick"),
          ("sample_tick", "完成步接点拍", "1", "sample_tick"),
          ("omega", "轮速", "rad/s", "omega"), ("fx", "纵向力", "N", "fx"),
          ("fy", "侧向力", "N", "fy"), ("grip", "附着力上限", "N", "sample_grip"))
      for index, wheel in enumerate(("fl", "fr", "rl", "rr"))),
    *(Signal(f"{field}_{wheel}", f"{label} {wheel.upper()}", unit,
             f"Snapshot.player.wheel_dynamics[{index}].{attribute}; final force substep except step work")
      for field, label, unit, attribute in (
          ("mz", "接触区回正力矩", "N·m", "aligning_moment"),
          ("trail", "接触区拖距", "m", "pneumatic_trail"),
          ("contact_steering_work", "本拍接触转向输入功", "J", "contact_steering_work"))
      for index, wheel in enumerate(("fl", "fr", "rl", "rr"))),
    *(Signal(f"sample_load_{wheel}", f"完成步轮荷 {wheel.upper()}", "N",
             f"Snapshot.player.wheel_contacts[{index}].normal_load")
      for index, wheel in enumerate(("fl", "fr", "rl", "rr"))),
    *(Signal(f"utilization_{wheel}", f"末子步附着利用率 {wheel.upper()}", "1",
             f"hypot(wheel_dynamics[{index}].fx, fy)/force_grip; road_support and grip>0 only")
      for index, wheel in enumerate(("fl", "fr", "rl", "rr"))),
    *(Signal(f"abs_{wheel}", f"ABS {wheel.upper()}", "bool",
             f"Snapshot.player.brake_states[{index}].abs_active")
      for index, wheel in enumerate(("fl", "fr", "rl", "rr"))),
    *(Signal(f"pressure_{wheel}", f"制动压力比例 {wheel.upper()}", "1",
             f"Snapshot.player.brake_states[{index}].pressure")
      for index, wheel in enumerate(("fl", "fr", "rl", "rr"))),
)
SIGNAL_BY_KEY = {signal.key: signal for signal in SIGNALS}
PRE_ALIGN_SIGNAL_KEYS = set(SIGNAL_BY_KEY) - {f"{key}_{wheel}"
    for key in ("mz", "trail", "contact_steering_work") for wheel in ("fl", "fr", "rl", "rr")}
LEGACY_SIGNAL_KEYS = {"time", "tick", "speed", "ax", "ay", "yaw", "steering", "steering_request",
                      "throttle", "brake", "engine_throttle", "throttle_request", "brake_request",
                      "gear", "rpm", "clutch", "clutch_request", "gear_request", "path_error"} | {
    f"{field}_{wheel}" for field in ("kappa", "load", "omega", "fx", "fy", "grip", "abs", "pressure")
    for wheel in ("fl", "fr", "rl", "rr")}


def sample_signals(snapshot, command, start_time):
    player = snapshot.player
    horizontal_speed = math.hypot(*player.velocity[:2])
    values = {"time": snapshot.time-start_time, "tick": snapshot.tick, "speed": player.speed*3.6,
              "ax": player.acceleration, "ay": player.lateral_acceleration,
              "yaw": player.dynamics.yaw_rate, "steering": player.steering,
              "steering_request": command.steering, "throttle": player.throttle,
              "brake": player.brake, "throttle_request": command.throttle,
              "brake_request": command.brake, "gear": player.gear, "rpm": player.rpm}
    values.update(horizontal_speed=horizontal_speed,
                  beta=player.dynamics.sideslip if horizontal_speed > 1 else None, roll=player.roll)
    values["clutch"] = player.powertrain_state.clutch_position if player.powertrain_state is not None else None
    values["engine_throttle"] = player.powertrain_state.throttle if player.powertrain_state is not None else None
    values["clutch_request"], values["gear_request"] = command.clutch, command.gear
    for index, wheel in enumerate(("fl", "fr", "rl", "rr")):
        state = player.wheel_dynamics[index]
        for key, value in (("kappa", state.kappa), ("load", state.normal_load),
                           ("alpha", state.alpha), ("force_grip", state.force_grip),
                           ("force_residual", state.force_residual),
                           ("force_tick", state.force_contact_tick), ("sample_tick", state.sample_tick),
                           ("omega", state.omega), ("fx", state.fx), ("fy", state.fy),
                           ("grip", state.sample_grip)):
            values[f"{key}_{wheel}"] = value
        values[f"mz_{wheel}"] = state.aligning_moment
        values[f"trail_{wheel}"] = state.pneumatic_trail
        values[f"contact_steering_work_{wheel}"] = state.contact_steering_work
        values[f"sample_load_{wheel}"] = player.wheel_contacts[index].normal_load
        values[f"utilization_{wheel}"] = (math.hypot(state.fx, state.fy)/state.force_grip
                                         if state.road_support and state.force_grip > 0 else None)
        values[f"abs_{wheel}"] = player.brake_states[index].abs_active
        values[f"pressure_{wheel}"] = player.brake_states[index].pressure
    for axle, left, right in (("front", "fl", "fr"), ("rear", "rl", "rr")):
        total = values[f"sample_load_{left}"] + values[f"sample_load_{right}"]
        values[f"ltr_{axle}"] = ((values[f"sample_load_{right}"]-values[f"sample_load_{left}"])/total
                                 if total > 0 else None)
    return values
