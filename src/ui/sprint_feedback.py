"""短途路线的目标、分段与失败提示；只格式化完成步结果。"""

from math import ceil

from sprint_routes import sprint_result_route


def goals(route):
    return " / ".join(f"{medal}{seconds:g}" for medal, seconds in zip(("金", "银", "铜"), route.targets, strict=True))+" 秒"


def driving_feedback(result):
    route = sprint_result_route(result)
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
            remaining = f"测速门{ceil(route.gates[0]-result.position)}m · ≥{route.entry_kph:g}km/h"
        elif result.position < zone.start:
            remaining = (f"距限速带{ceil(zone.start-result.position)}m"
                         f" · 入带{zone.minimum_kph:g}–{zone.maximum_kph:g}km/h")
        elif result.position <= zone.end:
            remaining = (f"限速{zone.minimum_kph:g}–{zone.maximum_kph:g} · {result.forward_kph:.1f}km/h"
                         f" · 出口{ceil(zone.end-result.position)}m")
        else:
            remaining = "已通过限速带 · 重新加速冲线"
    return detail, goals(route)+"\n"+remaining


def result_feedback(result):
    route = sprint_result_route(result)
    best = f"最佳 {result.best_seconds:.3f}s" if result.best_seconds is not None else "暂无有效最佳"
    note = ("新个人最佳 · " if result.new_best else "")+result.reason
    if result.save_notice:
        note += "\n"+result.save_notice
    detail = f"本次 {result.seconds:.3f}s · {best}\n{goals(route)}"
    if result.zone_min_kph is not None:
        detail += f"\n限速带实测 {result.zone_min_kph:.2f}–{result.zone_max_kph:.2f}km/h"
    return note, detail


def valley_braking_feedback(result, reference=None):
    route = sprint_result_route(result)
    zone = route.speed_zone
    gate = f'测速 {result.gate_kph[0]:.1f}km/h' if result.gate_kph else '测速门前'
    pedal = '减速区' if result.braking_request is None else f'平均踏板 {result.braking_request:.0%}'
    entry = '限速带' if result.zone_entry_kph is None else f'入带 {result.zone_entry_kph:.1f}km/h'
    if result.succeeded and reference is not None and result.braking_request is not None:
        gate_delta = result.gate_kph[0]-reference.gate_kph
        zone_delta = result.zone_entry_kph-reference.zone_entry_kph
        pedal_delta = (result.braking_request-reference.braking_request)*100
        gate += f' ({gate_delta:+.1f})' if abs(gate_delta) >= .05 else ' (0.0)'
        entry += f' ({zone_delta:+.1f})' if abs(zone_delta) >= .05 else ' (0.0)'
        points = f'{pedal_delta:+.0f}' if abs(pedal_delta) >= .5 else '0'
        pedal = f'踏板 {result.braking_request:.0%} ({points}百分点)'
    hint = ''
    if result.finished and not result.succeeded:
        if result.gate_kph and result.gate_kph[0] < route.entry_kph:
            hint = f'先达到{route.entry_kph:g}km/h，过测速门再制动'
        elif result.zone_error_at == zone.start and result.zone_entry_kph is not None:
            if result.zone_entry_kph < zone.minimum_kph:
                hint = '入带过慢，提前松刹'
            elif result.zone_entry_kph > zone.maximum_kph:
                hint = (f'测速门尽量贴近{route.entry_kph:g}km/h' if result.braking_request is not None
                        and result.braking_request >= .9 else '过测速门后尽快加大制动')
        elif result.zone_error_at is not None:
            hint = f'入带后稳住{zone.minimum_kph:g}–{zone.maximum_kph:g}km/h'
    return (gate, pedal, entry, '出带冲线'), hint


def result_columns(result):
    route = sprint_result_route(result)
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
