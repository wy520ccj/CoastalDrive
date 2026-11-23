"""从同条件重复真人试跑复算候选门槛；不把自动试车或旧缺测数据当真人。"""

import math
from dataclasses import asdict
from decimal import ROUND_CEILING, Decimal
from types import SimpleNamespace

from challenge_build import PRICE_VERSION, BuildDraft
from challenge_rules import MEDALS, MedalTarget
from challenge_trace import TRACE_COLUMNS
from fuel import FUEL_MODEL_VERSION, FUEL_STEP_COLUMNS, FuelMeter
from powertrain import engine_torque
from race import GameMode, RaceTracker


def _same_number(a, b):
    return type(a) in (int, float) and math.isfinite(a) and math.isclose(a, b, rel_tol=1e-10, abs_tol=1e-10)


def replay_fuel(spec, document):
    """从每个已接受机械子步的原始输入重算耗油，不信任累计量和结果摘要。"""
    if tuple(document['fuel_step_columns']) != FUEL_STEP_COLUMNS:
        raise ValueError('燃油原始子步字段不完整')
    rows, steps = document['samples'], document['fuel_steps']
    if len(steps) != len(rows) or steps[0]:
        raise ValueError('燃油子步须与发车后每个真实120Hz完成步对应')
    config = spec.configuration(BuildDraft(**document['build']))
    meter = FuelMeter(config.idle_rpm, config.engine_redline_rpm)
    meter.litres = document['start_litres']
    for index, group in enumerate(steps[1:], 1):
        duration = work = 0.
        for step in group:
            if (len(step) != len(FUEL_STEP_COLUMNS) or type(step[-1]) is not bool
                    or any(type(value) not in (int, float) or not math.isfinite(value) for value in step[:-1])
                    or not 0 < step[4] <= 1/120):
                raise ValueError('燃油子步包含无效计量输入')
            active_work, before, after, full_torque, dt, coupled = step
            rpm = max(0., (before+after)*30/math.tau)
            if not _same_number(full_torque, engine_torque(rpm, config)):
                raise ValueError('燃油负荷基准与本次实际发动机曲线不一致')
            meter.accept(active_work, before, after, full_torque, dt, coupled=coupled)
            duration += dt
            work += active_work
        if not _same_number(duration, 1/120) or not _same_number(work, rows[index][7]):
            raise ValueError('燃油子步时长或主动功与实际120Hz完成步不一致')
        if not _same_number(meter.litres, rows[index][3]) or not _same_number(meter.rate_lph, rows[index][4]):
            raise ValueError('燃油累计量或流率不能由真实机械子步复算')
    return meter.snapshot()


def checked_sample(spec, document, *, agent=False):
    circuit = spec.id == GameMode.TIME_TRIAL.value
    wrong_controller = (document['controller'] == 'keyboard' if agent else document['controller'] != 'keyboard')
    if (document['version'] != (3 if circuit else 2) or document['physics_hz'] != 120
            or document['price_version'] != PRICE_VERSION or document['fuel_version'] != FUEL_MODEL_VERSION
            or wrong_controller or spec.assessment != 'road'):
        raise ValueError('标定须使用当前计量版本、指定驾驶来源的完整道路挑战')
    if document['source_start'] != document['source_end']:
        raise ValueError('试跑首末源码或SDK改变，不能用作标定样本')
    # JSON中的tuple为list；结构化值相同才属于相同原车、预算和规则。
    import json

    if document['spec'] != json.loads(json.dumps(asdict(spec))):
        raise ValueError('试跑关卡条件与当前目录不同')
    if tuple(document['columns']) != TRACE_COLUMNS:
        raise ValueError('缺少完整逐拍原始计量与控制输入')
    build = BuildDraft(**document['build'])
    result = document['result']
    expected = spec.evaluate(build, result['seconds'], result['litres'])
    if not result['valid'] or result['official'] == agent or not expected.official:
        raise ValueError('无效、超预算或驾驶来源不符，不能用作该类基准')
    rows = document['samples']
    if len(rows) < 2 or rows[0][0] != document['initial_tick'] or rows[0][1] != 0.:
        raise ValueError('缺少发车原始状态')
    if rows[0][3] != document['start_litres']:
        raise ValueError('发车燃油量与起点不一致')
    for index, row in enumerate(rows):
        if (len(row) != len(TRACE_COLUMNS) or any(type(value) not in (int, float)
              or not math.isfinite(value) for value in row)
                or row[0] != document['initial_tick']+index or not _same_number(row[1], index/120)
                or not -1 <= row[9] <= 1 or not 0 <= row[10] <= 1 or not 0 <= row[11] <= 1
                or row[12] not in (-1, 1) or index and row[3] < rows[index-1][3]):
            raise ValueError('原始完成步或输入不连续/无效')
    replay_fuel(spec, document)
    before, after = rows[-2:]
    if circuit:
        time = replay_circuit(document)
        fraction = (time-before[1])/(after[1]-before[1])
    else:
        crossing = next((index for index, row in enumerate(rows) if row[2] >= spec.distance_m), None)
        if crossing != len(rows)-1:
            raise ValueError('记录须在首次有效终点所在完成步结束')
        fraction = (spec.distance_m-before[2])/(after[2]-before[2])
        time = before[1]+(after[1]-before[1])*fraction
    litres = before[3]+(after[3]-before[3])*fraction-document['start_litres']
    if not _same_number(result['seconds'], time) or not _same_number(result['litres'], litres):
        raise ValueError('结算不符合真实终点所在步的时间和耗油复算')
    if not _same_number(result['consumption'], litres*100_000/spec.distance_m):
        raise ValueError('赛段油耗没有按规定路线长度折算')
    return {'build': asdict(build), 'seconds': time, 'consumption': litres*100_000/spec.distance_m,
            'source': document['source_start'], 'input_group': document['input_group']}


def replay_circuit(document):
    """只用实际完成步位置重跑门线规则，不创建物理世界或以摘要代替过线。"""
    frames, rows = document['circuit_frames'], document['samples']
    if len(frames) != len(rows):
        raise ValueError('环路原始位置须对应每个真实完成步')
    race = RaceTracker(GameMode.TIME_TRIAL, record_scores=False)
    race.begin()
    for index, frame in enumerate(frames):
        if len(frame) != 4 or any(type(value) not in (int, float) or not math.isfinite(value) for value in frame):
            raise ValueError('环路位置或车速无效')
        if index:
            race.update(SimpleNamespace(player=SimpleNamespace(position=frame[:3], speed=frame[3])), 1/120)
        if not _same_number(race.distance, rows[index][2]):
            raise ValueError('环路进度不能由原始位置复算')
        if race.snapshot.finished and index != len(frames)-1:
            raise ValueError('记录须在首次有效环路终点所在完成步结束')
    lap = race.snapshot
    if not lap.finished or lap.invalidated:
        raise ValueError('原始位置未有效通过环路全部门线')
    if len(document['splits']) != len(lap.splits) or any(
            not _same_number(split['seconds'], seconds)
            for split, seconds in zip(document['splits'], lap.splits, strict=True)):
        raise ValueError('环路分段不符合原始门线时刻')
    return lap.elapsed


def candidate_targets(spec, documents, *, source, agent=False):
    if any(document['source_start'] != source for document in documents):
        raise ValueError('试跑样本与当前游戏源码或SDK不同，不能用于本版本标定')
    samples = [checked_sample(spec, document, agent=agent) for document in documents]
    if agent and len({document['controller'] for document in documents}) != 1:
        raise ValueError('代理基准须由同一驾驶控制器产生，不混用不同自动策略')
    if len(samples) < 4:
        raise ValueError('至少需要两套不同方案各两次完整'+('代理' if agent else '真人')+'试跑')
    ids = [document['run_id'] for document in documents]
    if (any(not isinstance(run_id, str) or len(run_id) != 32 for run_id in ids)
            or len(set(ids)) != len(ids)):
        raise ValueError('须使用不同次真实试跑，不能重复提供同一份记录')
    first = samples[0]
    if any(row['source'] != first['source'] or row['input_group'] != first['input_group'] for row in samples):
        raise ValueError('真人样本的源码/SDK或输入条件不同')
    groups = {}
    for row in samples:
        key = tuple(row['build'].values())
        groups.setdefault(key, []).append(row)
    if len(groups) < 2 or any(len(group) < 2 for group in groups.values()):
        raise ValueError('须提供至少两套有重复试跑的不同工程方案')

    def upward(value):
        return float((value*10).to_integral_value(rounding=ROUND_CEILING)/10)

    # 取选定可重复方案的保守值，金牌留3%，银铜在金牌基础放宽12%/30%。
    gold_time = Decimal(str(max(row['seconds'] for row in samples)))*Decimal('1.03')
    gold_oil = Decimal(str(max(row['consumption'] for row in samples)))*Decimal('1.03')
    gold_time, gold_oil = Decimal(str(upward(gold_time))), Decimal(str(upward(gold_oil)))
    return tuple(MedalTarget(medal, upward(gold_time*factor), upward(gold_oil*factor))
                 for medal, factor in zip(MEDALS, (Decimal('1.30'), Decimal('1.12'), Decimal(1))))
