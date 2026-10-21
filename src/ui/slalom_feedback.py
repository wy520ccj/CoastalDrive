"""连续过门的具体下一目标、偏差与成绩提示。"""

from slalom_lesson import ENTRY_DISTANCE, GATES

RULES = ("封闭直线 · 无车流 · 当前车辆/原驾驶辅助\n80米入口至少40km/h；左右连续6门到320米\n"
         "整车俯视包络须在4米门宽内，碰撞/复位失败\n入口后≤15秒金 / ≤18秒银 / ≤24秒铜；全程40秒")


FAST_RULES = ('高速验车 · 当前硬件与原驾驶辅助 · 无车流\n80米入口至320米终点，全段70–80km/h\n'
              '原六门/4米门宽，整车留在线内；碰撞/复位失败\n入口后≤11.5秒金 / ≤12.5秒银 / ≤14秒铜\n'
              '先在普通练习掌握路线，再比较轮胎/防倾配方\n更大刚度未必全面更好；返回实验台查看侧偏代价')


def driving_feedback(result, *, fast=False):
    if result is None:
        if fast:
            return '80米入口 · 全段70–80km/h\n左右连续6门到320米', '准备高速验车；先看清入口和第1道左门'
        return "80米入口 ≥40km/h\n左右连续6门到320米", "准备出发；先看清入口和第1道左门"
    if result.entry_time is None:
        if result.practice:
            return f'过门练习 · 距入口 {max(0, ENTRY_DISTANCE-result.position):.0f}m\n不限起步速度', '按W加速，A/D转向；漏门可继续练习'
        entry = '70–80 km/h' if result.fast else '≥40 km/h'
        return f"距入口 {max(0, ENTRY_DISTANCE-result.position):.0f} m\n入门要求 {entry}", "先加速，看到下一道门再转向"
    index = min(len(result.gate_times), len(GATES)-1)
    distance, center = GATES[index]
    direction = "终点居中" if index == len(GATES)-1 else "左侧" if center < 0 else "右侧"
    detail = f"已过 {result.gates} / 6门 · {result.run_seconds:.2f}s\n第{index+1}门 {direction} · 剩余{max(0, distance-result.position):.0f}m"
    message = "提前看下一门；过门前回正，急弯稍松油门"
    if result.practice:
        message = '漏门可继续；先找到节奏，再挑战奖牌'
    if result.fast:
        message = '全段70–80km/h；提前连贯转向，勿减到普通练习车速'
        if result.zone_min_kph is not None:
            message += f' · 实测{result.zone_min_kph:.1f}–{result.zone_max_kph:.1f}km/h'
    if result.save_notice:
        message += " · "+result.save_notice
    return detail, message


def result_feedback(result):
    if result.practice:
        return result.reason, f'通过 {result.gates}/6门 · 本次漏门 {len(result.clearances)-result.gates}\n练习不记录奖牌，可用不同配方再试'
    entry = f"{result.entry_kph:.1f}km/h" if result.entry_kph is not None else "未过入口"
    best = f"最佳 {result.best_seconds:.3f}s" if result.best_seconds is not None else "暂无成功成绩"
    lines = [f"入门 {entry} · 已过 {result.gates}/6门", f"入口后 {result.run_seconds:.3f}s · {best}"]
    if result.errors:
        index = len(result.errors)
        lines.append(f"第{index}门中心误差 {result.errors[-1]:+.2f}m / 车身余量 {result.clearances[-1]:+.2f}m")
    note = ("个人新最佳 · " if result.new_best else "")+result.reason+("\n"+result.save_notice if result.save_notice else "")
    if result.fast and result.zone_min_kph is not None:
        lines.append(f'全段实测 {result.zone_min_kph:.1f}–{result.zone_max_kph:.1f}km/h / 要求70–80')
    return note, "\n".join(lines)


def gate_feedback(result):
    if result is None or not result.gate_times:
        return "等待首门逐门反馈\n同一配置的完整个人最佳作对照"
    index = len(result.gate_times)-1
    seconds = result.gate_times[index]-(result.gate_times[index-1] if index else 0.)
    title = f"第{index+1}门 · 余量 {result.clearances[index]:+.2f}m"
    if result.finished and not result.succeeded:
        return title+"\n本次未完成，不更新个人最佳"
    if result.practice:
        return title+f'\n本次通过 {result.gates}/6门 · 漏门可继续'
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
