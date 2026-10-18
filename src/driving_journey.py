"""短课题成长直接派生自已保存成绩，不另存一份进度。"""

from braking_lesson import medal_for as braking_medal
from slalom_lesson import medal_for as slalom_medal

MEDALS = ("", "铜", "银", "金")


def read_driving_journey(braking, slalom):
    projects = []
    errors = []
    for topic, title, score, award, targets, unit in (
        ("braking", "定点刹停", braking, braking_medal, (10., 5., 2.), "m"),
        ("slalom", "连续过门", slalom, slalom_medal, (24., 18., 15.), "s"),
    ):
        best = score.best
        level = MEDALS.index(award(best)) if best is not None else 0
        target = targets[level] if level < 3 else None
        projects.append({"topic": topic, "title": title, "best": best, "medal": MEDALS[level],
            "level": level, "targets": targets, "unit": unit, "target": target,
            "gap": max(0., best-target) if best is not None and target is not None else None})
        if score.notice:
            errors.append(f"{title}：{score.notice}")
    # 两项都达到这一档再建议下一档；单项已拿金仍可补另一项。
    next_index = min(range(2), key=lambda index: projects[index]["level"])
    steps = sum(item["level"] for item in projects)
    return {"projects": projects, "steps": steps, "next_index": next_index if steps < 6 else None,
        "stage": ("铜牌起步", "银牌进阶", "金牌冲刺", "双项金牌")[min(item["level"] for item in projects)],
        "errors": errors}
