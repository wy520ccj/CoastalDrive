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
    note = result.reason+("\n"+result.save_notice if result.save_notice else "")
    return note, "\n".join(lines)
