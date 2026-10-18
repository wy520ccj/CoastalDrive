"""定点刹停的驾驶提示与结算文字。"""

from braking_lesson import ENTRY_DISTANCE, TARGET_DISTANCE, medal_for

RULES = "留在三车道内 · 无车流 · 使用当前车辆\n100米测速门至少80km/h；停在170米目标\n停稳后松开刹车，保持1秒；限时30秒\n按车身中心：±2米金 / ±5米银 / ±10米铜"


def driving_feedback(result):
    if result is None:
        return "100米测速门 ≥80km/h\n目标中心 170米", "加速过门，再选择制动时机"
    if result.entry_kph is None:
        detail = f"距测速门 {max(0, ENTRY_DISTANCE-result.position):.0f} m\n入门要求 ≥80 km/h"
        message = "先加速过橙色测速门；蓝色区域是停车区"
    else:
        detail = f"入门 {result.entry_kph:.1f} km/h\n距目标 {TARGET_DISTANCE-result.position:+.1f} m"
        message = (f"松开刹车，停稳 {result.hold_seconds:.1f} / 1.0秒" if result.hold_seconds > 0
                   else "选择制动时机，将车身中心停在目标线")
    if result.save_notice:
        message += " · "+result.save_notice
    return detail, message


def result_feedback(result):
    error = f"{result.error_m:+.2f} m" if result.error_m is not None else "未完成停车"
    entry = f"{result.entry_kph:.1f} km/h" if result.entry_kph is not None else "尚未过门"
    best = f"最佳误差 ±{result.best_error:.2f} m · {medal_for(result.best_error)}牌" if result.best_error is not None else "暂无成功成绩"
    detail = f"入门速度 {entry}\n停车误差 {error}（负数偏早，正数偏晚）\n{best}"
    note = result.reason + ("\n"+result.save_notice if result.save_notice else "")
    return note, detail
