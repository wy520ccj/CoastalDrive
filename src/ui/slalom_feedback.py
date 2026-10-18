"""连续过门的具体下一目标、偏差与成绩提示。"""

from slalom_lesson import ENTRY_DISTANCE, GATES

RULES = ("封闭直线 · 无车流 · 当前车辆/原驾驶辅助\n80米入口至少40km/h；左右连续6门到320米\n"
         "整车俯视包络须在4米门宽内，碰撞/复位失败\n入口后≤15秒金 / ≤18秒银 / ≤24秒铜；全程40秒")


def driving_feedback(result):
    if result is None:
        return "80米入口 ≥40km/h\n左右连续6门到320米", "准备出发；先看清入口和第1道左门"
    if result.entry_time is None:
        return f"距入口 {max(0, ENTRY_DISTANCE-result.position):.0f} m\n入门要求 ≥40 km/h", "先加速，看到下一道门再转向"
    index = min(result.gates, len(GATES)-1)
    distance, center = GATES[index]
    direction = "终点居中" if index == len(GATES)-1 else "左侧" if center < 0 else "右侧"
    detail = f"已过 {result.gates} / 6门 · {result.run_seconds:.2f}s\n第{index+1}门 {direction} · 剩余{max(0, distance-result.position):.0f}m"
    message = "提前看下一门；过门前回正，急弯稍松油门"
    if result.save_notice:
        message += " · "+result.save_notice
    return detail, message


def result_feedback(result):
    entry = f"{result.entry_kph:.1f}km/h" if result.entry_kph is not None else "未过入口"
    best = f"最佳 {result.best_seconds:.3f}s" if result.best_seconds is not None else "暂无成功成绩"
    lines = [f"入门 {entry} · 已过 {result.gates}/6门", f"入口后 {result.run_seconds:.3f}s · {best}"]
    if result.errors:
        index = len(result.errors)
        lines.append(f"第{index}门中心误差 {result.errors[-1]:+.2f}m / 车身余量 {result.clearances[-1]:+.2f}m")
    note = ("个人新最佳 · " if result.new_best else "")+result.reason+("\n"+result.save_notice if result.save_notice else "")
    return note, "\n".join(lines)


def gate_feedback(result):
    if result is None or not result.gate_times:
        return "等待首门逐门反馈\n同一配置的完整个人最佳作对照"
    index = len(result.gate_times)-1
    seconds = result.gate_times[index]-(result.gate_times[index-1] if index else 0.)
    title = f"第{index+1}门 · 余量 {result.clearances[index]:+.2f}m"
    if result.finished and not result.succeeded:
        return title+"\n本次未完成，不更新个人最佳"
    delta = (f"累计差 {result.gate_times[index]-result.reference_times[index]:+.3f}s"
             if result.reference_times else "暂无同配置逐门最佳")
    return title+f"\n本段 {seconds:.3f}s · {delta}"


def gate_columns(result):
    labels, times, margins = ["门 / 偏差m"], ["累计 / s"], ["余量m / ΔPBs"]
    for index, (_, center) in enumerate(GATES):
        direction = "左" if center < 0 else "右" if center > 0 else "中"
        if index >= len(result.gate_times):
            labels.append(f"{index+1}{direction} · 未到达")
            times.append("—")
            margins.append("— / —")
            continue
        failed = result.clearances[index] < 0
        labels.append(f"{index+1}{direction}{'漏' if failed else ''} {result.errors[index]:+.2f}")
        times.append(f"{result.gate_times[index]:.3f}")
        delta = (f"{result.gate_times[index]-result.reference_times[index]:+.3f}"
                 if result.reference_times and not (result.finished and not result.succeeded) else "—")
        margins.append(f"{result.clearances[index]:+.2f} / {delta}")
    return tuple("\n".join(column) for column in (labels, times, margins))
