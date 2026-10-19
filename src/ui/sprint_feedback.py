"""短途路线的目标、分段与失败提示；只格式化完成步结果。"""

from race import GameMode
from sprint_routes import SPRINT_ROUTES


def goals(route):
    return " / ".join(f"{medal}{seconds:g}" for medal, seconds in zip(("金", "银", "铜"), route.targets, strict=True))+" 秒"


def driving_feedback(result):
    route = SPRINT_ROUTES[GameMode(result.route_id)]
    index = min(result.gates, len(route.gates)-1)
    target = "终点" if index+1 == len(route.gates) else f"第{index+1}门"
    detail = f"已过 {result.gates}/{len(route.gates)}门 · {result.position:.0f}m\n距{target} {max(0., route.gates[index]-result.position):.0f}m"
    target_time = next((seconds for seconds in route.targets if seconds >= result.seconds), None)
    remaining = f"目标余时 {target_time-result.seconds:.1f}s" if target_time is not None else "继续完成，仍可保存有效成绩"
    if result.gate_times:
        index = len(result.gate_times)-1
        delta = f" · ΔPB {result.gate_times[index]-result.reference_times[index]:+.2f}s" if result.reference_times else ""
        remaining = f"第{index+1}门 {result.gate_times[index]:.2f}s"+delta
    zone = route.speed_zone
    if zone is not None:
        if result.position < route.gates[0]:
            remaining = f"首门至少{route.entry_kph:g}km/h · 当前{result.forward_kph:.1f}"
        elif result.position < zone.start:
            remaining = f"距限速带{zone.start-result.position:.0f}m · 提前减至{zone.minimum_kph:g}–{zone.maximum_kph:g}"
        elif result.position <= zone.end:
            remaining = f"限速带{zone.minimum_kph:g}–{zone.maximum_kph:g} · 当前{result.forward_kph:.1f}km/h"
        else:
            remaining = "已通过限速带 · 重新加速冲线"
    return detail, goals(route)+"\n"+remaining


def result_feedback(result):
    route = SPRINT_ROUTES[GameMode(result.route_id)]
    best = f"最佳 {result.best_seconds:.3f}s" if result.best_seconds is not None else "暂无有效最佳"
    note = ("新个人最佳 · " if result.new_best else "")+result.reason
    if result.save_notice:
        note += "\n"+result.save_notice
    detail = f"本次 {result.seconds:.3f}s · {best}\n{goals(route)}"
    if result.zone_min_kph is not None:
        detail += f"\n限速带实测 {result.zone_min_kph:.2f}–{result.zone_max_kph:.2f}km/h"
    return note, detail


def result_columns(result):
    route = SPRINT_ROUTES[GameMode(result.route_id)]
    labels, times, deltas = ["道路门"], ["累计 / s"], ["比出发时最佳 / s"]
    if route.speed_zone is not None:
        deltas[0] = "过门 km/h / ΔPBs"
    for index, distance in enumerate(route.gates):
        labels.append(f"{index+1} · {distance:.0f}m")
        times.append(f"{result.gate_times[index]:.3f}" if index < len(result.gate_times) else "—")
        delta = (f"{result.gate_times[index]-result.reference_times[index]:+.3f}"
                 if result.reference_times and index < result.gates and not (result.finished and not result.succeeded) else "—")
        deltas.append(f"{result.gate_kph[index]:.1f} / {delta}"
                      if route.speed_zone is not None and index < len(result.gate_kph) else delta)
    return tuple("\n".join(column) for column in (labels, times, deltas))
