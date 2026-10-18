"""第二道教学工坊：同速定圆循迹、侧偏约束与预算取舍。"""

import hashlib
import json
import math
from dataclasses import asdict, replace

from lab_experiment import LabOptions
from lab_maneuvers import path_error
from vehicle_designs import REFERENCE_DESIGN
from vehicle_state import FIXED_DT

CHALLENGE_ID = "coastal-cornering-v1"
OPTIONS = LabOptions(maneuver="constant_radius", speed_kph=60., radius_m=40., duration=10.)
BASE_CONFIG = replace(REFERENCE_DESIGN, lateral_stiffness=35000.,
    suspension_antiroll_rates=(28000., 2000.),
    stability=replace(REFERENCE_DESIGN.stability, esc_enabled=False))
FRONT_STIFFNESS = (35000., 45000., 50000., 70000.)
TIRE_COST = (0, 1, 2, 2)
BUDGET = 3
TAIL_START = 8.


def build_config(tire_index, balanced_bar, lower_cg):
    if type(tire_index) is not int or not 0 <= tire_index < len(FRONT_STIFFNESS):
        raise ValueError("请选择有效的前胎侧偏配方")
    if type(balanced_bar) is not bool or type(lower_cg) is not bool:
        raise ValueError("防倾与重心选项须为布尔值")
    return replace(BASE_CONFIG, lateral_stiffness=FRONT_STIFFNESS[tire_index],
        suspension_antiroll_rates=(8000., 22000.) if balanced_bar else BASE_CONFIG.suspension_antiroll_rates,
        center_of_mass_height=.32 if lower_cg else BASE_CONFIG.center_of_mass_height)


def cost(tire_index, balanced_bar, lower_cg):
    build_config(tire_index, balanced_bar, lower_cg)
    return TIRE_COST[tire_index] + int(balanced_bar) + 3*lower_cg


def config_digest(config):
    return hashlib.sha256(json.dumps(asdict(config), sort_keys=True, allow_nan=False).encode()).hexdigest()


def record_metrics(record):
    """由原始完成步复算，避免只修改导出摘要/曲线就获得任务成绩。"""
    metadata, states = record.metadata, record.snapshots
    summary = metadata["summary"]
    if (metadata["runtime_profile"] != "reference" or summary["reason"] != "time_limit"
            or summary["options"] != asdict(OPTIONS)
            or metadata["source_start"] != metadata["source_end"]
            or metadata["runtime_start"] != metadata["runtime_end"]
            or len(states) != 1201 or summary["ticks"] != 1200):
        raise ValueError("须在固定60km/h、40m半径条件下完成10秒参考试验")
    initial = states[0]
    if abs(math.hypot(*initial.player.velocity[:2])*3.6-OPTIONS.speed_kph) > .01:
        raise ValueError("试验初速不是规定的60km/h")
    driver = metadata["driver"]
    expected_driver = {"kind": "pure_pursuit_speed_pi", "preview_seconds": 1.2,
                       "minimum_preview_m": 6., "speed_p": .2, "speed_i": .08}
    if not isinstance(driver, dict) or any(driver.get(key) != value for key, value in expected_driver.items()):
        raise ValueError("试验驾驶员不是本题固定的循迹/速度控制器")
    tail = []
    beta, roll = [], []
    for index, state in enumerate(states):
        elapsed = state.time-initial.time
        if (state.tick != initial.tick+index or abs(elapsed-index*FIXED_DT) > 1e-9
                or state.collisions != initial.collisions or "player_reset" in state.events):
            raise ValueError("试验完成步不连续，或存在碰撞/复位")
        values = (*state.player.velocity, state.player.dynamics.sideslip, state.player.roll,
                  state.player.steering, *state.player.position)
        if any(not math.isfinite(value) for value in values):
            raise ValueError("操稳试验包含非有限状态")
        beta.append(abs(state.player.dynamics.sideslip))
        roll.append(abs(state.player.roll))
        if elapsed >= TAIL_START-1e-9:
            tail.append((path_error(OPTIONS, state.player, initial.player),
                         math.hypot(*state.player.velocity[:2])*3.6, abs(state.player.steering)))
    return {"mean_error_m": sum(abs(row[0]) for row in tail)/len(tail),
            "mean_signed_error_m": sum(row[0] for row in tail)/len(tail),
            "mean_speed_kph": sum(row[1] for row in tail)/len(tail),
            "max_speed_error_kph": max(abs(row[1]-OPTIONS.speed_kph) for row in tail),
            "mean_steering_deg": sum(row[2] for row in tail)/len(tail),
            "peak_beta_deg": max(beta), "peak_roll_deg": max(roll)}


def grade(baseline_error, metrics, points):
    if baseline_error <= 0 or not math.isfinite(baseline_error):
        raise ValueError("基线循迹误差须为有限正数")
    improvement = 100*(1-metrics["mean_error_m"]/baseline_error)
    unmet = []
    for condition, message in ((points > BUDGET, "预算超出"), (improvement < 50., "误差改善不足50%"),
            (metrics["mean_error_m"] > 1.6, "末窗误差超过1.6m"),
            (metrics["max_speed_error_kph"] > 1.2, "末窗车速超出60±1.2km/h"),
            (metrics["peak_beta_deg"] > 4., "峰值侧偏超过4°"),
            (metrics["peak_roll_deg"] > 3., "峰值侧倾超过3°")):
        if condition:
            unmet.append(message)
    passed = not unmet
    medal = ("金" if improvement >= 65. and points <= 2 else "银" if improvement >= 55. else "铜") if passed else None
    return improvement, passed, medal, unmet


def evaluate(baseline, candidate, tire_index, balanced_bar, lower_cg):
    config = build_config(tire_index, balanced_bar, lower_cg)
    for record, expected in ((baseline, BASE_CONFIG), (candidate, config)):
        if record.metadata["vehicle_config"] != json.loads(json.dumps(asdict(expected))):
            raise ValueError("实际硬件不是本题原车或当前选定方案")
    if (baseline.metadata["source_start"] != candidate.metadata["source_start"]
            or baseline.metadata["runtime_start"] != candidate.metadata["runtime_start"]):
        raise ValueError("A/B源码或运行库不同，请重新运行挑战")
    old, new = record_metrics(baseline), record_metrics(candidate)
    if old["max_speed_error_kph"] > 1.2:
        raise ValueError("基线未保持指定车速，请检查原始记录")
    points = cost(tire_index, balanced_bar, lower_cg)
    improvement, passed, medal, unmet = grade(old["mean_error_m"], new, points)
    return {"challenge_id": CHALLENGE_ID, "tire_index": tire_index, "balanced_bar": balanced_bar,
        "lower_cg": lower_cg, "cost": points, "baseline_metrics": old, "candidate_metrics": new,
        "improvement_pct": improvement, "passed": passed, "medal": medal, "unmet": unmet,
        "config_digest": config_digest(config), "road_validated": False}


def validate_receipt(receipt, config):
    expected = build_config(receipt["tire_index"], receipt["balanced_bar"], receipt["lower_cg"])
    points = cost(receipt["tire_index"], receipt["balanced_bar"], receipt["lower_cg"])
    fields = ("mean_error_m", "mean_signed_error_m", "mean_speed_kph", "max_speed_error_kph",
              "mean_steering_deg", "peak_beta_deg", "peak_roll_deg")
    for values in (receipt["baseline_metrics"], receipt["candidate_metrics"]):
        for key in fields:
            if type(values[key]) not in (int, float) or not math.isfinite(values[key]):
                raise ValueError("操稳成绩指标无效")
        if any(values[key] < 0 for key in fields if key != "mean_signed_error_m"):
            raise ValueError("操稳成绩非负指标无效")
        if (abs(values["mean_signed_error_m"]) > values["mean_error_m"]+1e-9
                or abs(values["mean_speed_kph"]-OPTIONS.speed_kph) > values["max_speed_error_kph"]+1e-9):
            raise ValueError("操稳成绩的平均值与绝对界限不一致")
    if (type(receipt["cost"]) is not int or type(receipt["improvement_pct"]) not in (int, float)
            or not math.isfinite(receipt["improvement_pct"])
            or receipt["baseline_metrics"]["max_speed_error_kph"] > 1.2):
        raise ValueError("操稳成绩预算/改善量或基线速度无效")
    improvement, passed, medal, unmet = grade(receipt["baseline_metrics"]["mean_error_m"],
                                             receipt["candidate_metrics"], points)
    if (not passed or receipt["passed"] is not True or receipt["medal"] != medal
            or receipt["unmet"] != unmet or receipt["cost"] != points
            or abs(receipt["improvement_pct"]-improvement) > 1e-10
            or config != expected or receipt["config_digest"] != config_digest(config)
            or type(receipt["road_validated"]) is not bool):
        raise ValueError("操稳成绩未满足任务目标或与硬件不一致")
