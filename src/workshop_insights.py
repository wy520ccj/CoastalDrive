"""从工坊真实A/B解释收益与代价；建议只准备选项，不改评分或物理。"""

import html
import json
import math
from itertools import pairwise

import workshop
import workshop_cornering as cornering
from vehicle_state import FIXED_DT, VehicleCommand

VERSION = 'workshop-insights-v1'


def braking_observations(record):
    states, summary = record.snapshots, record.metadata['summary']
    if len(states) < 2 or len(states) != summary['ticks']+1:
        raise ValueError('制动解读需要完整的120Hz原始快照')
    if (len(record.commands) != len(states) or record.commands[0] != VehicleCommand(gear=0, clutch=0.)
            or any(command != VehicleCommand(brake=1., gear=0, clutch=0.) for command in record.commands[1:])):
        raise ValueError('制动解读需要相同的全制动、零转向与动力分离请求')
    initial = states[0]
    for index, state in enumerate(states):
        car = state.player
        values = (*car.position, *car.velocity, car.dynamics.yaw_rate)
        if (state.tick != initial.tick+index or abs(state.time-initial.time-index*FIXED_DT) > 1e-9
                or state.collisions != initial.collisions or 'player_reset' in state.events
                or any(not math.isfinite(value) for value in values)):
            raise ValueError('制动完成步不连续、含碰撞/复位或无效数值')
    distance = sum(math.dist(a.player.position, b.player.position) for a, b in pairwise(states))
    yaw = max(abs(state.player.dynamics.yaw_rate) for state in states)
    if (abs(math.hypot(*initial.player.velocity[:2])*3.6-workshop.OPTIONS.speed_kph) > .01
            or math.hypot(*states[-1].player.velocity[:2]) > .1
            or not math.isclose(distance, summary['stopping_distance_m'], abs_tol=1e-8, rel_tol=0.)
            or not math.isclose(yaw, summary['peak_yaw_rate_radps'], abs_tol=1e-10, rel_tol=0.)):
        raise ValueError('制动摘要与原始初速、停稳、路径或横摆快照不一致')
    completed = states[1:]
    duty = []
    for axle in ((0, 1), (2, 3)):
        value = (100*sum(any(state.player.brake_states[i].abs_active for i in axle) for state in completed)/len(completed)
                 if all(len(state.player.brake_states) == 4 for state in completed) else None)
        duty.append(value)
    return {'distance_m': distance, 'peak_yaw': yaw, 'front_abs_pct': duty[0], 'rear_abs_pct': duty[1]}


def next_trial(topic, selection, result):
    """一次只改变当前B的一项；改善结果仍须按固定原车A重跑验证。"""
    proposed = None
    if topic == 0:
        share, large = selection
        if result['cost'] > workshop.BUDGET:
            proposed = (share, False)
            reason = '先撤回大制动器，释放3点预算，验证现有制动分配能否独立达标。'
        elif result['passed']:
            reason = '本次已达标；先保存并道路验证，观察同一套硬件的实际驾驶表现。'
        elif result['peak_yaw_radps'] > .05:
            reason = '先查看横摆与左右轮制动曲线，保持配方复测方向稳定性，再评价缩距。'
        else:
            proposed = (share+1 if share < 3 else 2, large)
            reason = '下一次只调整前制动份额，比较前后轴ABS介入与停车距离。'
        points = workshop.cost(*proposed) if proposed is not None else None
    else:
        tire, bar, lower = selection
        metrics = result['candidate_metrics']
        if lower and not result['passed']:
            proposed = (tire, bar, False)
            reason = '降低重心仍未达标；先撤回这项3点改动，释放后续轮胎试验的预算。'
        elif result['passed']:
            reason = '本次已达标；先保存并道路验证，把循迹改善与实际驾驶表现对照。'
        elif metrics['peak_beta_deg'] > 4. and tire > 0:
            proposed = (tire-1, bar, lower)
            reason = '侧偏超过4°；下一次只降低一档前胎配方，核对侧偏和循迹误差的取舍。'
        elif tire < 2:
            proposed = (tire+1, bar, lower)
            reason = '下一次只提高一档前胎侧偏配方，比较循迹误差、车速和侧偏变化。'
        elif not bar:
            proposed = (tire, True, lower)
            reason = '下一次只调整防倾分配，保持总刚度，核对循迹和侧倾变化。'
        else:
            reason = '先查看末窗车速和转向曲线，保持配方复测，再决定单项调整。'
        points = cornering.cost(*proposed) if proposed is not None else None
    if proposed is not None:
        assert sum(a != b for a, b in zip(selection, proposed, strict=True)) == 1
        reason += f'只改当前B一项，A仍为固定原车；重跑后才有新结论。下一B预算{points}/3。'
    return {'text': reason, 'selection': proposed, 'cost': points}


def describe(baseline, candidate, topic, selection):
    selection = tuple(selection)
    changes, rows = [], []
    if topic == 0:
        result = workshop.evaluate(baseline, candidate, *selection)
        old, new = braking_observations(baseline), braking_observations(candidate)
        share, large = selection
        if share:
            changes.append(f'前制动份额 45% → {workshop.BRAKE_SHARES[share]:.0%}')
        if large:
            changes.append(f'制动扭矩 {workshop.BASE_CONFIG.brake_torque:g} → {workshop.build_config(*selection).brake_torque:g} N·m')
        primary = ('停车距离', result['baseline_m'], result['candidate_m'], 'm')
        rows = [('前轴ABS介入采样', old['front_abs_pct'], new['front_abs_pct'], '%'),
                ('后轴ABS介入采样', old['rear_abs_pct'], new['rear_abs_pct'], '%'),
                ('峰值横摆', old['peak_yaw'], new['peak_yaw'], 'rad/s')]
        basis = 'ABS为完成拍至少一轮介入的轴比例，排除初始拍；介入更多不直接等于制动更好。路径与横摆由快照复算。'
        unmet = [text for condition, text in ((result['cost'] > 3, '预算超出'),
                 (result['improvement_pct'] < 10., '缩距不足10%'),
                 (result['peak_yaw_radps'] > .05, '横摆超限')) if condition]
    elif topic == 1:
        result = cornering.evaluate(baseline, candidate, *selection)
        old, new = result['baseline_metrics'], result['candidate_metrics']
        tire, bar, lower = selection
        if tire:
            changes.append(f'前轴侧偏刚度 35 → {cornering.FRONT_STIFFNESS[tire]/1000:g} kN/rad')
        if bar:
            changes.append('前/后防倾 28/2 → 8/22 kN/m（总刚度保持）')
        if lower:
            changes.append('重心高度 0.42 → 0.32 m')
        primary = ('末2秒平均循迹误差', old['mean_error_m'], new['mean_error_m'], 'm')
        rows = [('峰值车身侧偏', old['peak_beta_deg'], new['peak_beta_deg'], '°'),
                ('峰值车身侧倾', old['peak_roll_deg'], new['peak_roll_deg'], '°'),
                ('末窗最大车速偏差', old['max_speed_error_kph'], new['max_speed_error_kph'], 'km/h'),
                ('末窗平均实际转角', old['mean_steering_deg'], new['mean_steering_deg'], '°')]
        basis = '循迹/车速/实际转角取8–10秒末窗，侧偏/侧倾取全程快照绝对峰值；末窗车速条件单独检查。'
        unmet = result['unmet']
    else:
        raise ValueError('未知工坊题目')
    count = len(changes)
    attribution = ('本次保留原配，用于确认基线表现。' if count == 0 else
                   '同条件只改一项，本模型内差值对应这项改动。' if count == 1 else
                   f'本次同时改了{count}项，只能解释组合结果；不能把全部收益归给其中一项。')
    outcome = f"通过 · {result['medal']}牌" if result['passed'] else '未达标 · '+' / '.join(unmet)
    return {'version': VERSION, 'topic': topic, 'selection': selection, 'challenge_id': result['challenge_id'],
            'outcome': outcome, 'passed': result['passed'], 'changes': changes or ['保留原配'],
            'primary': primary, 'improvement_pct': result['improvement_pct'], 'rows': rows,
            'cost': result['cost'], 'budget': 3, 'attribution': attribution, 'basis': basis,
            'next': next_trial(topic, selection, result), 'config_digest': result['config_digest'],
            'record_ticks': [baseline.metadata['summary']['ticks'], candidate.metadata['summary']['ticks']]}


def row_text(row):
    label, a, b, unit = row
    if a is None or b is None:
        return f'{label}：旧快照未定义'
    return f'{label}  A {a:.3f} → B {b:.3f} {unit}（B−A {b-a:+.3f}）'


def text_report(data):
    return '\n'.join(['工坊试验解读 · '+data['outcome'], '改动：'+'；'.join(data['changes']),
        row_text(data['primary']), f"改善{data['improvement_pct']:+.2f}% · 预算{data['cost']}/{data['budget']}",
        *(row_text(row) for row in data['rows']), data['attribution'], data['basis'], '下一步：'+data['next']['text']])


def export_insights(data, folder):
    """与原始A/B同目录导出；文件失败由调用界面处理，不改奖牌或车辆。"""
    text = text_report(data)
    (folder/'insights.json').write_text(json.dumps(data, ensure_ascii=False, indent=2, allow_nan=False), encoding='utf-8')
    (folder/'insights.txt').write_text(text+'\n', encoding='utf-8')
    report = folder/'report.html'
    document = report.read_text(encoding='utf-8')
    if not document.rstrip().endswith('</html>'):
        raise ValueError('原始实验报告格式不完整，未追加解读')
    document = document.rsplit('</html>', 1)[0]+'<h2>工坊试验解读</h2><pre>'+html.escape(text)+'</pre></html>'
    report.write_text(document, encoding='utf-8')
