"""实验信号的单位和真实字段来源；接触未定义值保留None。"""

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
          ("kappa", "滑移率", "1", "kappa"), ("load", "法向载荷", "N", "normal_load"),
          ("omega", "轮速", "rad/s", "omega"), ("fx", "纵向力", "N", "fx"),
          ("fy", "侧向力", "N", "fy"), ("grip", "附着力上限", "N", "sample_grip"))
      for index, wheel in enumerate(("fl", "fr", "rl", "rr"))),
    *(Signal(f"abs_{wheel}", f"ABS {wheel.upper()}", "bool",
             f"Snapshot.player.brake_states[{index}].abs_active")
      for index, wheel in enumerate(("fl", "fr", "rl", "rr"))),
    *(Signal(f"pressure_{wheel}", f"制动压力比例 {wheel.upper()}", "1",
             f"Snapshot.player.brake_states[{index}].pressure")
      for index, wheel in enumerate(("fl", "fr", "rl", "rr"))),
)
SIGNAL_BY_KEY = {signal.key: signal for signal in SIGNALS}


def sample_signals(snapshot, command, start_time):
    player = snapshot.player
    values = {"time": snapshot.time-start_time, "tick": snapshot.tick, "speed": player.speed*3.6,
              "ax": player.acceleration, "ay": player.lateral_acceleration,
              "yaw": player.dynamics.yaw_rate, "steering": player.steering,
              "steering_request": command.steering, "throttle": player.throttle,
              "brake": player.brake, "throttle_request": command.throttle,
              "brake_request": command.brake, "gear": player.gear, "rpm": player.rpm}
    values["clutch"] = player.powertrain_state.clutch_position if player.powertrain_state is not None else None
    values["engine_throttle"] = player.powertrain_state.throttle if player.powertrain_state is not None else None
    values["clutch_request"], values["gear_request"] = command.clutch, command.gear
    for index, wheel in enumerate(("fl", "fr", "rl", "rr")):
        state = player.wheel_dynamics[index]
        for key, value in (("kappa", state.kappa), ("load", state.normal_load),
                           ("omega", state.omega), ("fx", state.fx), ("fy", state.fy),
                           ("grip", state.sample_grip)):
            values[f"{key}_{wheel}"] = value
        values[f"abs_{wheel}"] = player.brake_states[index].abs_active
        values[f"pressure_{wheel}"] = player.brake_states[index].pressure
    return values
