"""从已有试验和驾驶成绩派生初章进度，不另存一套完成标记。"""

import json
from dataclasses import asdict
from pathlib import Path

from braking_lesson import medal_for
from lab_records import load_record
from vehicle_schemes import checked_challenge, list_schemes
from workshop import CHALLENGE_ID as BRAKING_ID
from workshop_budget import REFERENCE_CHALLENGES
from workshop_cornering import CHALLENGE_ID as CORNERING_ID


def current_trial(vehicle):
    if vehicle.report_path is None:
        raise ValueError("当前工程车缺少原始试验报告")
    folder = Path(vehicle.report_path).parent
    record, baseline = load_record(folder), load_record(folder/"baseline-A")
    actual = checked_challenge(vehicle.workshop_result, baseline, record)
    if record.metadata["vehicle_config"] != json.loads(json.dumps(asdict(vehicle.config))):
        raise ValueError("当前工程车与原始试验硬件不一致")
    return actual


def read_journey(root, vehicle, scores):
    schemes, errors = list_schemes(root)
    projects = []
    for topic, challenge_id, title in ((0, BRAKING_ID, "01 制动配方"), (1, CORNERING_ID, "02 弯道循迹")):
        ids = (challenge_id, REFERENCE_CHALLENGES[topic].id)
        candidates = [(item.name, item.vehicle, item.id, item) for item in schemes
                      if item.vehicle.workshop_result is not None
                      and item.vehicle.workshop_result["challenge_id"] in ids]
        if (vehicle.workshop_result is not None and vehicle.workshop_result["challenge_id"] in ids
                and all(item[1] != vehicle for item in candidates)):
            candidates.append(("当前工程车", vehicle, vehicle.scheme_id, None))
        candidates.sort(key=lambda item: (item[1].workshop_result["road_validated"],
                        {"铜": 1, "银": 2, "金": 3}[item[1].workshop_result["medal"]]), reverse=True)
        chosen = None
        for name, candidate, identity, saved in candidates:
            try:
                saved.records() if saved is not None else current_trial(candidate)
            except (OSError, ValueError, KeyError, TypeError) as error:
                errors.append(f"{name}：{error}")
                continue
            chosen = (name, candidate, identity)
            break
        receipt = chosen[1].workshop_result if chosen else None
        steps = 0 if receipt is None else 2 if receipt["road_validated"] else 1
        projects.append({"topic": topic, "title": title, "steps": steps,
            "medal": receipt["medal"] if receipt else "", "scheme_id": chosen[2] if chosen else None,
            "vehicle": chosen[1] if chosen else None, "name": chosen[0] if chosen else "",
            "next": "完成固定条件A/B并保存通过方案" if steps == 0 else
                    "驾驶同一方案，完成滨海有效圈" if steps == 1 else "已完成试验与道路，可继续比较新方案"})
    best = scores.best
    medal = medal_for(best) if best is not None else ""
    projects.append({"topic": 2, "title": "03 定点刹停", "steps": int(best is not None),
                     "medal": medal, "best_error": best,
                     "next": "当前车辆以≥80km/h过门，停车误差≤10m" if best is None else
                             "挑战更准的停车点，金牌目标≤2m" if medal != "金" else "已完成当前车辆金牌，可重试保持手感"})
    if scores.notice:
        errors.append(scores.notice)
    completed = sum(item["steps"] for item in projects)
    next_index = next((index for index, item in enumerate(projects)
                       if item["steps"] < (2 if index < 2 else 1)), None)
    return {"projects": projects, "steps": completed, "next_index": next_index, "errors": errors}
