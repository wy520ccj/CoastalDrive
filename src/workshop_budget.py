"""固定参考A/B共用工程参数和报价；历史离散配方仅用于旧报告复核。"""

import json
import math
from dataclasses import asdict, dataclass

import workshop
import workshop_cornering as cornering
from challenge_build import PRICE_VERSION, BuildDraft
from lab_experiment import LabOptions
from vehicle_config import VehicleConfig
from workshop_insights import braking_observations

VERSION = 'reference-budget-v1'


@dataclass(frozen=True)
class ReferenceChallenge:
    id: str
    name: str
    base_config: VehicleConfig
    budget: int
    allowed: tuple[str, ...]
    options: LabOptions
    requirements: tuple[str, ...]
    conditions: str
    version: str = VERSION
    design_id: str = 'reference-rwd'
    assessment: str = 'reference'

    def configuration(self, build):
        return build.build(self.base_config, allowed=self.allowed)


REFERENCE_CHALLENGES = (
    ReferenceChallenge('reference-braking-budget-v1', '制动改装', workshop.BASE_CONFIG, 1500,
        ('brakes', 'brake_share', 'mass'), workshop.OPTIONS,
        ('缩距≥10%', '缩距≥11%', '缩距≥12%'), '80–0 km/h · 峰值横摆≤0.05 rad/s'),
    ReferenceChallenge('reference-cornering-budget-v1', '弯道改装', cornering.BASE_CONFIG, 2500,
        ('front_tire', 'rear_tire', 'springs', 'dampers', 'antiroll_share'), cornering.OPTIONS,
        ('误差减少≥50%', '误差减少≥55%', '误差减少≥65%'),
        '60 km/h · R40m · 误差≤1.6m\n车速±1.2km/h · 侧偏≤4° · 侧倾≤3°'),
)
REFERENCE_BY_ID = {spec.id: spec for spec in REFERENCE_CHALLENGES}


def _checked_metrics(topic, values):
    fields = (('distance_m', 'peak_yaw', 'front_abs_pct', 'rear_abs_pct') if topic == 0 else
              ('mean_error_m', 'mean_signed_error_m', 'mean_speed_kph', 'max_speed_error_kph',
               'mean_steering_deg', 'peak_beta_deg', 'peak_roll_deg'))
    for key in fields:
        value = values[key]
        if key in ('front_abs_pct', 'rear_abs_pct') and value is None:
            continue
        if (type(value) not in (int, float) or not math.isfinite(value)
                or key != 'mean_signed_error_m' and value < 0):
            raise ValueError('参考专项实测值无效')


def _grade(topic, baseline, candidate, cost):
    spec = REFERENCE_CHALLENGES[topic]
    old = baseline['distance_m'] if topic == 0 else baseline['mean_error_m']
    new = candidate['distance_m'] if topic == 0 else candidate['mean_error_m']
    if old <= 0 or not math.isfinite(old):
        raise ValueError('原装基线须为有限正值')
    improvement = 100*(1-new/old)
    unmet = ['超出本场预算'] if cost > spec.budget else []
    if topic == 0:
        conditions = ((improvement < 10., '停车改善不足10%'),
                      (candidate['peak_yaw'] > .05, '峰值横摆超过0.05rad/s'))
        silver, gold = 11., 12.
    else:
        conditions = ((improvement < 50., '误差改善不足50%'),
            (new > 1.6, '末窗误差超过1.6m'),
            (candidate['max_speed_error_kph'] > 1.2, '末窗车速超出60±1.2km/h'),
            (candidate['peak_beta_deg'] > 4., '峰值侧偏超过4°'),
            (candidate['peak_roll_deg'] > 3., '峰值侧倾超过3°'))
        silver, gold = 55., 65.
    unmet.extend(message for failed, message in conditions if failed)
    medal = None if unmet else '金' if improvement >= gold else '银' if improvement >= silver else '铜'
    return improvement, medal, unmet


def evaluate(topic, baseline, candidate, build):
    if type(topic) is not int or topic not in (0, 1):
        raise ValueError('未知参考工坊题目')
    spec = REFERENCE_CHALLENGES[topic]
    config = spec.configuration(build)
    for record, expected in ((baseline, spec.base_config), (candidate, config)):
        data = record.metadata
        if (data['runtime_profile'] != 'reference' or data['summary']['options'] != asdict(spec.options)
                or data['vehicle_config'] != json.loads(json.dumps(asdict(expected)))
                or data['source_start'] != data['source_end'] or data['runtime_start'] != data['runtime_end']):
            raise ValueError('工坊须在固定原车、所选完整硬件和相同参考条件下真实完成')
    if (baseline.metadata['source_start'] != candidate.metadata['source_start']
            or baseline.metadata['runtime_start'] != candidate.metadata['runtime_start']):
        raise ValueError('A/B源码或SDK不同，请重新试验')
    if topic == 0:
        if any(record.metadata['summary']['reason'] != 'stopped' for record in (baseline, candidate)):
            raise ValueError('固定制动试验须真实停稳')
        old, new = braking_observations(baseline), braking_observations(candidate)
    else:
        old, new = cornering.record_metrics(baseline), cornering.record_metrics(candidate)
        if old['max_speed_error_kph'] > 1.2:
            raise ValueError('原车基线未保持规定车速，请检查原始记录')
    _checked_metrics(topic, old)
    _checked_metrics(topic, new)
    improvement, medal, unmet = _grade(topic, old, new, build.cost)
    return {'challenge_id': spec.id, 'rules_version': VERSION, 'price_version': PRICE_VERSION,
            'build': asdict(build), 'cost': build.cost, 'budget': spec.budget,
            'baseline_metrics': old, 'candidate_metrics': new, 'improvement_pct': improvement,
            'passed': medal is not None, 'medal': medal, 'unmet': unmet,
            'config_digest': workshop.config_digest(config), 'road_validated': False}


def validate_receipt(receipt, config):
    spec = REFERENCE_BY_ID[receipt['challenge_id']]
    topic = REFERENCE_CHALLENGES.index(spec)
    build = BuildDraft(**receipt['build'])
    if (receipt['rules_version'] != VERSION or receipt['price_version'] != PRICE_VERSION
            or receipt['cost'] != build.cost or receipt['budget'] != spec.budget
            or config != spec.configuration(build) or receipt['config_digest'] != workshop.config_digest(config)
            or type(receipt['road_validated']) is not bool):
        raise ValueError('预算工坊成绩与车辆、报价或规则版本不一致')
    for values in (receipt['baseline_metrics'], receipt['candidate_metrics']):
        _checked_metrics(topic, values)
    improvement, medal, unmet = _grade(topic, receipt['baseline_metrics'], receipt['candidate_metrics'], build.cost)
    if (not medal or receipt['passed'] is not True or receipt['medal'] != medal or unmet
            or receipt['improvement_pct'] != improvement):
        raise ValueError('预算工坊成绩没有达到实际专项要求')


def describe(topic, baseline, candidate, build):
    result = evaluate(topic, baseline, candidate, build)
    old, new = result['baseline_metrics'], result['candidate_metrics']
    if topic == 0:
        primary = ('停车距离', old['distance_m'], new['distance_m'], 'm')
        rows = [('峰值横摆', old['peak_yaw'], new['peak_yaw'], 'rad/s'),
                ('前轴ABS介入', old['front_abs_pct'], new['front_abs_pct'], '%'),
                ('后轴ABS介入', old['rear_abs_pct'], new['rear_abs_pct'], '%')]
    else:
        primary = ('末窗循迹误差', old['mean_error_m'], new['mean_error_m'], 'm')
        rows = [('峰值侧偏', old['peak_beta_deg'], new['peak_beta_deg'], '°'),
                ('峰值侧倾', old['peak_roll_deg'], new['peak_roll_deg'], '°'),
                ('末窗最大车速偏差', old['max_speed_error_kph'], new['max_speed_error_kph'], 'km/h'),
                ('末窗平均实际转角', old['mean_steering_deg'], new['mean_steering_deg'], '°')]
    return {**result, 'topic': topic, 'primary': primary, 'rows': rows,
            'outcome': result['medal']+'牌完成' if result['passed'] else '未达标 · '+' / '.join(result['unmet'])}
