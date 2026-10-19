"""安全超车的规则、赛中提示和完整结果。"""

from overtake_run import PASS_TARGET


def driving_feedback(result):
    remaining = max(0., 2000.-result.distance)
    return ((f"安全超车 {result.passes}/{PASS_TARGET} · 剩余{remaining:.0f}m\n"
             "侧距≥1m 或前后距≥10m"), result.feedback)


def result_feedback(result):
    best = f"当前车最佳 {result.best_seconds:.3f}s" if result.best_seconds is not None else "当前车暂无成功成绩"
    detail = f"安全超车 {result.passes}/{PASS_TARGET} · {result.seconds:.3f}s · {result.distance:.0f}m\n{best}"
    if result.new_best:
        detail += " · 新最佳"
    for index, (seconds, identity, clearance) in enumerate(zip(result.pass_times, result.pass_ids, result.pass_clearances, strict=True), 1):
        detail += f"\n第{index}辆 #{identity[0]+1} · {seconds:.3f}s · 并排最小侧距{clearance:.2f}m"
    if result.save_notice:
        detail += "\n"+result.save_notice
    return result.reason, detail
