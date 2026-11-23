"""离线实验会话；输入和120Hz时间推进独立于窗口与播放时钟。"""

import math
import sys
from dataclasses import asdict, dataclass, replace
from importlib import import_module
from itertools import pairwise
from pathlib import Path
from time import perf_counter

from panda3d.bullet import BulletBoxShape, BulletRigidBodyNode
from panda3d.core import BitMask32, TransformState, Vec3

from driving_experiment import DrivingExperiment, ExperimentOptions
from driving_modes import DrivingMode
from lab_inputs import LabInputError, active_fields, validate_number
from lab_maneuvers import (
    CIRCLE_BRAKING_MANEUVERS,
    PATH_MANEUVERS,
    bump_geometry,
    path_command,
    path_error,
)
from lab_metrics import (
    DELAYED_BRAKING_MANEUVERS,
    NEW_BRAKING_MANEUVERS,
    brake_start_index,
    cg_motion,
)
from lab_records import model_fingerprint
from lab_runtime import runtime_fingerprint
from lab_signals import sample_signals
from vehicle_contacts import read_wheel_contacts
from vehicle_designs import vehicle_design
from vehicle_state import FIXED_DT, VehicleCommand

MANEUVERS = {"braking": "直线制动", "step_steer": "阶跃转向", "circle": "固定转角",
             "sine_steer": "正弦转向", "manual": "执行器输入", "constant_radius": "定圆试验",
             "double_lane_change": "参考双移线", "split_braking": "对开附着制动", "ride_bump":"单侧凸起 / 轮跳",
             "ride_braking":"单侧凸起 / 制动",
             "cornering_braking": "定圆弯道制动", "step_steer_braking": "阶跃转向同步制动",
             "mu_jump_cornering_braking": "对接附着弯道制动"}

MU_JUMP_DISTANCE_M = 10.


@dataclass(frozen=True)
class LabOptions:
    vehicle_id: str = "reference-rwd"
    maneuver: str = "braking"
    speed_kph: float = 100.
    friction: float = 1.1
    abs_enabled: bool = True
    esc_enabled: bool = False
    duration: float = 12.
    steering_deg: float = 3.
    onset: float = .5
    seed: int = 0
    cg_height: float | None = None
    radius_m: float = 60.
    right_friction: float = .3
    tire_reference_load: float | None = None
    bump_height_m: float = .01
    bump_length_m: float = .9
    bump_distance_m: float = 6.
    controller_mode: str = "native"

    def __post_init__(self):
        vehicle_design(self.vehicle_id)
        if self.maneuver not in MANEUVERS:
            raise ValueError("未知试验工况")
        for key, value in (("speed", self.speed_kph), ("mu", self.friction),
                ("radius", self.radius_m), ("right_mu", self.right_friction),
                ("duration", self.duration), ("onset", self.onset),
                ("bump_height", self.bump_height_m), ("bump_length", self.bump_length_m),
                ("bump_distance", self.bump_distance_m)):
            validate_number(key, value)
        validate_number("steer", self.steering_deg)
        if self.cg_height is not None:
            validate_number("cg", self.cg_height)
        if self.tire_reference_load is not None:
            validate_number("tire_load", self.tire_reference_load)


LAB_DEFAULTS = LabOptions()


def load_coordinated_controller():
    """从同一暑期项目目录下的课程源码加载，原生模式无需课程依赖。"""
    homework = Path(__file__).resolve().parents[2] / "汽车理论" / "作业"
    source = homework / "cornering_braking_control" / "src" / "abs_dyc_controller.py"
    if not source.is_file():
        raise ValueError(f"缺少 ABS–DYC 协调控制器：{source}")
    import_root = str(homework)
    added = import_root not in sys.path
    if added:
        sys.path.insert(0, import_root)
    try:
        module = import_module("cornering_braking_control.src.abs_dyc_controller")
    except ModuleNotFoundError as error:
        raise ValueError(f"无法加载 ABS–DYC 协调控制器，缺少模块：{error.name}") from error
    finally:
        if added:
            sys.path.remove(import_root)
    return module.CoordinatedABSDYCController()


class LabExperiment:
    def __init__(self, options=LAB_DEFAULTS, *, config=None, parameter_metadata=None,
                 runtime_profile="reference", controller=None):
        if controller is None and options.controller_mode == "coord_abs_dyc":
            controller = load_coordinated_controller()
        self.options = options
        self.design = vehicle_design(options.vehicle_id)
        self.parameter_metadata = parameter_metadata
        if runtime_profile not in ("reference", "game"):
            raise ValueError("未知实验积分配置")
        self.runtime_profile = runtime_profile
        config = DrivingMode.SIMULATION.configured_vehicle(
            options.abs_enabled if controller is None else False,
            esc_enabled=options.esc_enabled if controller is None else False,
            base_config=self.design.config if config is None else config)
        config = replace(config, road_friction=options.friction)
        if options.maneuver in ("split_braking", "mu_jump_cornering_braking"):
            config = replace(config, grass_friction=options.right_friction,
                             grass_rolling_coefficient=config.rolling_coefficient)
        if options.cg_height is not None:
            config = replace(config, center_of_mass_height=options.cg_height)
        if options.tire_reference_load is not None:
            config = replace(config, tire_reference_load=options.tire_reference_load)
        if runtime_profile == "game":
            config = DrivingMode.GAME.configured_vehicle(base_config=config)
        self.config = config
        if "steer" in active_fields(options.maneuver) and abs(options.steering_deg) > config.steering_degrees:
            raise LabInputError("steer", f"目标转角须在当前模型的±{config.steering_degrees:g}°范围内。")
        if options.maneuver in ("ride_bump","ride_braking") and not config.unsprung_enabled:
            raise ValueError("轮跳/颠簸制动需要独立轮心模型，请先导入对应工程配置")
        self.source_start = model_fingerprint()
        self.runtime_start = runtime_fingerprint()
        self.controller = controller
        self.controller_telemetry = getattr(controller, "telemetry", None)
        self.experiment = DrivingExperiment(config, ExperimentOptions(seed=options.seed, track="lab"))
        self.compute_seconds = 0.
        self.error = None
        self.reason = None
        self.paused = True
        self.closed = False
        self.manual_command = VehicleCommand(gear=0, clutch=0.)
        self.speed_integral = 0.
        self.latched_steering = None
        self.braking_distance = 0.
        self.controller_trace = [None]
        try:
            simulation = self.experiment.simulation
            if options.maneuver == "split_braking":
                # 道路分类读取实际轮胎接触点x；车轮跨越分界线时随空间位置改变。
                boundary = simulation.spawn[0]
                simulation.on_asphalt = lambda x, y: x < boundary
            elif options.maneuver == "mu_jump_cornering_braking":
                # 完成拍累计质心水平路程，达阈值后下一拍四轮同时进入新附着。
                simulation.on_asphalt = lambda x, y: self.braking_distance < MU_JUMP_DISTANCE_M
            if options.maneuver in ("split_braking", "mu_jump_cornering_braking"):
                simulation.player.on_asphalt = simulation.on_asphalt
            simulation.settle_initial()
            initial_command = VehicleCommand(gear=0, clutch=0.)
            # 先在真实固定步释放落地锁车制动，再施加研究初速；不把预载压力带入试验。
            for _ in range(max(1, math.ceil(8*config.braking.response_time/FIXED_DT))):
                simulation.step(initial_command)
            if options.maneuver in ("ride_bump","ride_braking"):
                install_bump(simulation,options,config)
            # 只在初始化设置滚动初值；试验中的姿态/轮速全部由真实物理推进。
            player = simulation.player
            player.initialize_rolling(options.speed_kph/3.6)
            initial = simulation.snapshot()
            if not config.unsprung_enabled:
                player.tires.observe(player._chassis,
                    read_wheel_contacts(player._vehicle, player.on_asphalt), initial.tick)
            initial = simulation.snapshot()
            self.start_time = initial.time
            self.initial_collisions = initial.collisions
            self.snapshots = [initial]
            self.commands = [initial_command]
            self.samples = [sample_signals(initial, self.commands[0], self.start_time)]
            self.samples[0]["path_error"] = path_error(options, initial.player, initial.player)
            self.distance = 0.
            if controller is not None:
                controller.reset(config, options, initial)
        except Exception:
            self.experiment.close()
            raise

    @property
    def current(self):
        return self.snapshots[-1]

    @property
    def elapsed(self):
        return (len(self.snapshots)-1)*FIXED_DT

    @property
    def done(self):
        return self.reason is not None

    def command_at(self, time):
        options = self.options
        if options.maneuver == "manual":
            return self.manual_command
        if options.maneuver=="ride_bump":
            return VehicleCommand(gear=0,clutch=0.)
        if options.maneuver=="ride_braking":
            return VehicleCommand(gear=0,clutch=0.,brake=1. if time>=options.onset else 0.)
        if options.maneuver in PATH_MANEUVERS:
            if options.maneuver in CIRCLE_BRAKING_MANEUVERS:
                if time >= options.onset:
                    steering = self.current.player.steering if self.latched_steering is None else self.latched_steering
                    return VehicleCommand(steering=steering, brake=1., gear=0, clutch=0.)
                # 空挡滑行建立侧向加速度，避免高速自动挂挡反拖后轮。
                steering = path_command(options, self.current.player, self.snapshots[0].player,
                                        self.config, 0.).steering
                return VehicleCommand(steering=steering, throttle=0., brake=0., gear=0, clutch=0.)
            return path_command(options, self.current.player, self.snapshots[0].player,
                                self.config, self.speed_integral)
        steering, brake = 0., 0.
        if options.maneuver in ("braking", "split_braking"):
            brake = 1.
        elif time >= options.onset:
            steering = options.steering_deg
            if options.maneuver == "step_steer_braking":
                brake = 1.
            elif options.maneuver == "sine_steer":
                steering *= math.sin(2*math.pi*.5*(time-options.onset))
        return VehicleCommand(steering=steering, brake=brake, gear=0, clutch=0.)

    def step(self, command=None):
        """单步不受暂停按钮影响；每次严格完成一个外层机械拍。"""
        if self.closed or self.done:
            raise RuntimeError("实验已结束或关闭，请新建试验")
        maneuver = self.options.maneuver
        elapsed = self.elapsed
        after_onset = elapsed >= self.options.onset
        previous = self.current
        if maneuver in CIRCLE_BRAKING_MANEUVERS and after_onset and self.latched_steering is None:
            self.latched_steering = previous.player.steering
        if command is None:
            if maneuver in PATH_MANEUVERS and maneuver not in CIRCLE_BRAKING_MANEUVERS:
                error = self.options.speed_kph/3.6-self.current.player.speed
                self.speed_integral = max(-.1, min(.4, self.speed_integral+.08*error*FIXED_DT))
            command = self.command_at(elapsed)
        started = perf_counter()
        try:
            if self.controller is not None:
                command = self.controller.compute(previous, command, elapsed, FIXED_DT)
            self.experiment.simulation.step(command)
            state = self.experiment.simulation.snapshot()
            telemetry = None if self.controller_telemetry is None else dict(self.controller_telemetry())
        except (ArithmeticError, ValueError, RuntimeError) as error:
            self.reason, self.error, self.paused = "failed", str(error), True
            raise
        finally:
            self.compute_seconds += perf_counter()-started
        self.snapshots.append(state)
        self.commands.append(command)
        self.samples.append(sample_signals(state, command, self.start_time))
        if self.controller is not None:
            self.controller_trace.append(telemetry)
        self.samples[-1]["path_error"] = path_error(self.options, state.player, self.snapshots[0].player)
        self.distance += math.dist(previous.player.position, state.player.position)
        if maneuver == "mu_jump_cornering_braking" and after_onset:
            self.braking_distance += math.dist(cg_motion(previous.player)[0][:2], cg_motion(state.player)[0][:2])
        stop_check = (maneuver in ("braking", "split_braking")
                      or (maneuver == "ride_braking" and self.elapsed >= self.options.onset)
                      or (maneuver in NEW_BRAKING_MANEUVERS and after_onset))
        if state.collisions > self.initial_collisions:
            self.reason = "collision"
        elif "player_reset" in state.events:
            self.reason = "reset"
        elif stop_check:
            velocity = (cg_motion(state.player)[1] if maneuver in DELAYED_BRAKING_MANEUVERS
                        else state.player.velocity)
            if math.hypot(*velocity[:2]) <= .1:
                self.reason = "stopped"
        if self.reason is None and len(self.samples)-1 >= math.ceil(self.options.duration/FIXED_DT):
            self.reason = "time_limit"
        if self.done:
            self.paused = True
        return state

    def advance(self, budget_seconds=.006):
        """界面分批离线计算；预算只限制本帧工作量，不改变积分步或丢弃时间。"""
        if self.paused or self.done:
            return 0
        started, count = perf_counter(), 0
        while perf_counter()-started < budget_seconds and not self.done:
            self.step()
            count += 1
        return count

    def summary(self):
        errors = [abs(row["path_error"]) for row in self.samples if row["path_error"] is not None]
        summary = {"status": self.reason or ("paused" if self.paused else "running"),
                "reason": self.reason, "error": self.error,
                "simulation_seconds": self.elapsed, "compute_seconds": self.compute_seconds,
                "distance_m": self.distance,
                "stopping_distance_m": self.distance if self.reason == "stopped" else None,
                "peak_deceleration_mps2": min(row["ax"] for row in self.samples),
                "peak_lateral_acceleration_mps2": max(abs(row["ay"]) for row in self.samples),
                "peak_yaw_rate_radps": max(abs(row["yaw"]) for row in self.samples),
                "mean_path_error_m": sum(errors)/len(errors) if errors else None,
                "maximum_path_error_m": max(errors) if errors else None,
                "abs_ticks": sum(any(row[f"abs_{wheel}"] for wheel in ("fl", "fr", "rl", "rr"))
                                 for row in self.samples[1:]),
                "ticks": len(self.samples)-1, "initialization_ticks": self.snapshots[0].tick,
                "options": asdict(self.options)}
        if self.options.maneuver=="ride_braking":
            accelerations = [row["cg_ax"] for row in self.samples if row["cg_ax"] is not None]
            summary["peak_deceleration_mps2"] = min(accelerations) if accelerations else None
        if self.options.maneuver in DELAYED_BRAKING_MANEUVERS:
            index = brake_start_index(self.samples,self.options.maneuver)
            summary["braking_reference"] = None if index is None else {
                "time_s":self.samples[index]["time"],
                "speed_mps":math.hypot(*cg_motion(self.snapshots[index].player)[1][:2]),
                "distance_basis":"制动请求前样本至停止，整车质量加权CG水平路径"}
            summary["stopping_distance_m"] = None
            if self.reason=="stopped" and index is not None:
                positions = [cg_motion(s.player)[0] for s in self.snapshots[index:]]
                summary["stopping_distance_m"] = sum(math.dist(a[:2],b[:2]) for a,b in pairwise(positions))
        return summary

    def close(self):
        if not self.closed:
            self.experiment.close()
            self.closed = True


def install_bump(simulation, options, config):
    """左侧实体路面刺激；几何与碰撞留在唯一世界，运行中不移动道路或车轮。"""
    center, half = bump_geometry(options, simulation.player.reference_pose().getPos(), config)
    body = BulletRigidBodyNode("lab-left-bump")
    shape = BulletBoxShape(Vec3(*half))
    shape.setMargin(0.)
    body.addShape(shape)
    body.setTransform(TransformState.makePos(Vec3(*center)))
    body.setIntoCollideMask(BitMask32(7))
    simulation._world.attachRigidBody(body)
    simulation._prop_bodies.append(body)
