"""定点刹停的驾驶提示与结算文字。"""

from braking_lesson import ENTRY_DISTANCE, TARGET_DISTANCE, medal_for
from short_braking import medal_for as short_medal

RULES = "留在三车道内 · 无车流 · 使用当前车辆\n100米测速门至少80km/h；停在170米目标\n停稳后松开刹车，保持1秒；限时30秒\n按车身中心：±2米金 / ±5米银 / ±10米铜"
SHORT_RULES = ('短距制动验车 · 无车流 · 当前车辆/原辅助\n100米门须80–85km/h，过门后尽快制动\n'
               '中心横向≤1米 / 车头偏角≤5°，不得倒车\n松开S，停稳1秒；限时30秒\n'
               '过门后最大前进距离：≤33米金 / ≤36米银 / ≤42米铜\n成绩受入门车速与反应时机影响，纯硬件制动性能可在试验台对比')


def driving_feedback(result, *, short=False):
    if result is None:
        if short:
            return '100米门 · 80–85km/h\n过门后尽快停车', '准备短距制动；保持直行'
        return "100米测速门 ≥80km/h\n目标中心 170米", "加速过门，再选择制动时机"
    if result.short:
        detail = (f'距100米门 {max(0, ENTRY_DISTANCE-result.position):.0f}m\n入门须80–85km/h' if result.entry_kph is None else
                  f'入门{result.entry_kph:.1f}km/h\n过门后{result.stopping_m:.2f}m / 铜牌42m')
        return detail, (f'松开S · 停稳{result.hold_seconds:.1f}/1秒' if result.hold_seconds else
                        '过门后尽快制动；金33 / 银36 / 铜42米，保持直行')
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
    if result.short:
        entry = f'{result.entry_kph:.1f}km/h' if result.entry_kph is not None else '未过门'
        distance = f'{result.stopping_m:.2f}m' if result.stopping_m is not None else '未建立'
        best = f'最佳 {result.best_distance:.2f}m · {short_medal(result.best_distance)}牌' if result.best_distance is not None else '暂无成功成绩'
        return result.reason+('\n'+result.save_notice if result.save_notice else ''), (
            f'入门 {entry} · 过门后最大前进 {distance}\n{best}\n金33 / 银36 / 铜42米；包含驾驶反应')
    error = f"{result.error_m:+.2f} m" if result.error_m is not None else "未完成停车"
    entry = f"{result.entry_kph:.1f} km/h" if result.entry_kph is not None else "尚未过门"
    best = f"最佳误差 ±{result.best_error:.2f} m · {medal_for(result.best_error)}牌" if result.best_error is not None else "暂无成功成绩"
    detail = f"入门速度 {entry}\n停车误差 {error}（负数偏早，正数偏晚）\n{best}"
    note = result.reason + ("\n"+result.save_notice if result.save_notice else "")
    return note, detail
