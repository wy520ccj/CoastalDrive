"""滨海计时的固定玩法目标；奖牌从有效圈速派生，不改判圈。"""

import math

from race import GameMode

TARGETS = (("金", 55.), ("银", 65.), ("铜", 80.))
RULES = "金≤55s · 银≤65s · 铜≤80s"


def medal_for(seconds):
    if type(seconds) not in (int, float) or not math.isfinite(seconds) or seconds <= 0:
        return ""
    return next((medal for medal, limit in TARGETS if seconds <= limit), "")


def next_goal(best):
    for medal, limit in reversed(TARGETS):
        if best is None or best > limit:
            return medal+"牌", limit
    return "个人最佳", best


def menu_goal(best):
    title, limit = next_goal(best)
    medal = medal_for(best)
    comparison = "<" if title == "个人最佳" else "≤"
    return f"{medal+'牌 · ' if medal else ''}{title} {comparison}{limit:g}s"


def driving_goal(race):
    if race.invalidated:
        return RULES+"\n本圈无效 · 下次再争奖牌"
    title, limit = next_goal(race.reference_lap)
    remaining = limit-race.elapsed
    if remaining >= 0:
        detail = f"目标 {title} · 还剩{remaining:.1f}s"
    else:
        available = next((medal for medal, target in TARGETS if race.elapsed < target), "")
        detail = f"目标已超时 · 仍可争{available}牌" if available else "目标已超时 · 完成本圈再挑战"
    return RULES+"\n"+detail


def result_medal(race, track):
    if track != "coastal" or race.mode != GameMode.TIME_TRIAL or not race.finished or race.invalidated:
        return ""
    return medal_for(race.last_lap)


def result_goal(race):
    title, limit = next_goal(race.best_lap)
    comparison = "<" if title == "个人最佳" else "≤"
    if race.invalidated or race.last_lap is None:
        return f"下次目标 {title} {comparison}{limit:g}s"
    gap = race.last_lap-limit
    return (f"下一目标 {title} {comparison}{limit:g}s · 还差{gap:.3f}s" if gap > 0 else
            f"下一目标 {title} {comparison}{limit:g}s")
