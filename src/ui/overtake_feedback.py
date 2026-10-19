"""安全超车的规则、赛中提示和完整结果。"""

from overtake_routes import OVERTAKE_ROUTES
from race import GameMode


def driving_feedback(result):
    route = OVERTAKE_ROUTES[GameMode(result.route_id)]
    remaining = max(0., route.distance-result.distance)
    feedback = ("超车达标 · 保持间距驶过终点" if route.finish_at_end and result.passes >= route.passes else result.feedback)
    return ((f"安全超车 {result.passes}/{route.passes} · 剩余{remaining:.0f}m\n"
             "侧距≥1m 或前后距≥10m"), feedback)


def result_feedback(result):
    route = OVERTAKE_ROUTES[GameMode(result.route_id)]
    best = f"当前车最佳 {result.best_seconds:.3f}s" if result.best_seconds is not None else "当前车暂无成功成绩"
    detail = f"安全超车 {result.passes}/{route.passes} · {result.seconds:.3f}s · {result.distance:.0f}m\n{best}"
    if result.new_best:
        detail += " · 新最佳"
    for index, (seconds, identity, clearance) in enumerate(zip(result.pass_times, result.pass_ids, result.pass_clearances, strict=True), 1):
        detail += f"\n第{index}辆 #{identity[0]+1} · {seconds:.3f}s · 并排最小侧距{clearance:.2f}m"
    if result.save_notice:
        detail += "\n"+result.save_notice
    return result.reason, detail
