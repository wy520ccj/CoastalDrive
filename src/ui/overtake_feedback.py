"""安全超车的规则、赛中提示和完整结果。"""

from overtake_routes import OVERTAKE_ROUTES
from race import GameMode


def driving_feedback(result):
    route = OVERTAKE_ROUTES[GameMode(result.route_id)]
    remaining = max(0., route.distance-result.distance)
    feedback = ("超车达标 · 保持间距驶过终点" if route.finish_at_end and result.passes >= route.passes else result.feedback)
    return ((f"安全超车 {result.passes}/{route.passes} · 剩余{remaining:.0f}m\n"
             "侧距≥1m 或前后距≥10m"), feedback)


def traffic_feedback(result):
    reading = result.traffic_reading
    if reading is None:
        return '继续观察车流与空隙', False
    number = reading.identity[0]+1
    if reading.kind == 'front':
        trend = f'接近{reading.closing_kph:.0f}km/h' if reading.closing_kph > 0 else '间距保持或拉开'
        second = (f'匀速约{reading.seconds_to_limit:.1f}s到10m线' if reading.warning and reading.seconds_to_limit is not None
                  else trend+' · 至少留10m')
        return f'前方#{number} · 净距{reading.end_m:.1f}m\n'+second, reading.warning
    if reading.kind == 'clear':
        return f'后方#{number} · 整车领先{reading.end_m:.1f}m\n切回前至少拉开10m', reading.warning
    return (f"{'并行' if reading.kind == 'parallel' else '接近并排'}#{number} · 侧距{reading.side_m:.2f}m\n"
            f'距1m侧距线余{reading.side_m-1.:+.2f}m'), reading.warning


def incident_feedback(incident):
    phase = '拍间触发' if incident.between_ticks else '本拍触发'
    measured = (f'{phase} · {incident.seconds:.3f}s / {incident.distance:.0f}m\n'
                f'#{incident.identity[0]+1} 侧距{incident.side_m:.2f}m / 前后距{incident.end_m:.2f}m')
    advice = {'front': '下次更早收油或制动，跟车净距至少10m。',
              'parallel': '下次并行至少留1m侧距，保持横向空间。',
              'clear': '下次等整车领先10m，再向对方车道切回。'}[incident.kind]
    return measured+'\n'+advice+('\n拍间数值按原保守包络插值。' if incident.between_ticks else '')


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
    if result.incident is not None:
        detail += '\n'+incident_feedback(result.incident)
    return result.reason, detail
