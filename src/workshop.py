"""第一道工程挑战的固定条件、改装选项与真实试验评分。"""

import hashlib
import json
import math
from dataclasses import asdict, replace

import workshop_cornering
from lab_experiment import LabOptions
from race import GameMode
from vehicle_designs import REFERENCE_DESIGN

CHALLENGE_ID = "coastal-braking-v1"
OPTIONS = LabOptions(speed_kph=80., duration=12.)
BASE_CONFIG = replace(REFERENCE_DESIGN, front_brake_share=.45,
                      stability=replace(REFERENCE_DESIGN.stability, esc_enabled=False))
BRAKE_SHARES = (.45, .60, .70, .80)
BUDGET = 3


def build_config(share_index, large_brakes):
    if type(share_index) is not int or not 0 <= share_index < len(BRAKE_SHARES):
        raise ValueError("请选择有效的前制动份额")
    if type(large_brakes) is not bool:
        raise ValueError("制动器选项须为布尔值")
    return replace(BASE_CONFIG, front_brake_share=BRAKE_SHARES[share_index],
                   brake_torque=BASE_CONFIG.brake_torque*(1.4 if large_brakes else 1.))


def cost(share_index, large_brakes):
    build_config(share_index, large_brakes)
    return int(share_index != 0)+3*large_brakes


def config_digest(config):
    return hashlib.sha256(json.dumps(asdict(config), sort_keys=True,
                                    allow_nan=False).encode()).hexdigest()


def evaluate(baseline, candidate, share_index, large_brakes):
    """只接受本挑战同源、同条件、确实停车的两份原始记录。"""
    config = build_config(share_index, large_brakes)
    for record, expected in ((baseline, BASE_CONFIG), (candidate, config)):
        metadata, summary = record.metadata, record.metadata["summary"]
        if (metadata["runtime_profile"] != "reference" or summary["reason"] != "stopped"
                or summary["options"] != asdict(OPTIONS)
                or metadata["vehicle_config"] != json.loads(json.dumps(asdict(expected)))
                or metadata["source_start"] != metadata["source_end"]
                or metadata["runtime_start"] != metadata["runtime_end"]):
            raise ValueError("挑战须使用固定条件与所选硬件，完成真实停车后评价")
        for key in ("stopping_distance_m", "peak_yaw_rate_radps"):
            value = summary[key]
            if type(value) not in (int, float) or not math.isfinite(value) or value < 0:
                raise ValueError("试验指标无效")
    if (baseline.metadata["source_start"] != candidate.metadata["source_start"]
            or baseline.metadata["runtime_start"] != candidate.metadata["runtime_start"]):
        raise ValueError("A/B源码或运行库不同，请重新运行挑战")
    old, new = baseline.metadata["summary"], candidate.metadata["summary"]
    distance = old["stopping_distance_m"]
    if distance <= 0:
        raise ValueError("基线停车距离须为正值")
    improvement = 100*(distance-new["stopping_distance_m"])/distance
    points = cost(share_index, large_brakes)
    passed = improvement >= 10. and points <= BUDGET and new["peak_yaw_rate_radps"] <= .05
    medal = ("金" if improvement >= 12. and points <= 1 else "银" if improvement >= 12. else "铜") if passed else None
    return {"challenge_id": CHALLENGE_ID, "share_index": share_index, "large_brakes": large_brakes,
            "cost": points, "baseline_m": distance, "candidate_m": new["stopping_distance_m"],
            "improvement_pct": improvement, "peak_yaw_radps": new["peak_yaw_rate_radps"],
            "passed": passed, "medal": medal, "config_digest": config_digest(config),
            "road_validated": False}


def validate_receipt(receipt, config):
    """持久化边界检查；成绩只适用于实际通过的这套硬件。"""
    if receipt is None:
        return
    if isinstance(receipt, dict) and receipt.get("challenge_id") == workshop_cornering.CHALLENGE_ID:
        workshop_cornering.validate_receipt(receipt, config)
        return
    if not isinstance(receipt, dict) or receipt["challenge_id"] != CHALLENGE_ID:
        raise ValueError("未知工程挑战成绩")
    expected = build_config(receipt["share_index"], receipt["large_brakes"])
    for key in ("baseline_m", "candidate_m", "improvement_pct", "peak_yaw_radps"):
        if type(receipt[key]) not in (int, float) or not math.isfinite(receipt[key]):
            raise ValueError("工程成绩指标无效")
    if (receipt["baseline_m"] <= 0 or receipt["candidate_m"] <= 0
            or not 0 <= receipt["peak_yaw_radps"] <= .05
            or receipt["improvement_pct"] < 10.
            or abs(receipt["improvement_pct"]-100*(1-receipt["candidate_m"]/receipt["baseline_m"])) > 1e-10
            or receipt["cost"] != cost(receipt["share_index"], receipt["large_brakes"])
            or receipt["cost"] > BUDGET):
        raise ValueError("工程成绩未满足任务目标")
    if (config != expected or receipt["config_digest"] != config_digest(config)
            or receipt["passed"] is not True or receipt["medal"] not in ("金", "银", "铜")
            or type(receipt["road_validated"]) is not bool):
        raise ValueError("工程成绩与车辆硬件不一致")


def road_result(receipt, race, track):
    """道路只验证有效圈；不把键盘驾驶圈速当作参考试验复算。"""
    if (receipt is None or track != "coastal" or race.mode != GameMode.TIME_TRIAL
            or not race.finished or race.invalidated):
        return None
    if race.last_lap is None or not math.isfinite(race.last_lap) or race.last_lap <= 0:
        return None
    return {**receipt, "road_validated": True}
