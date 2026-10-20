"""用道路A/B的冻结硬件顺序运行参考试验；不改车辆、道路成绩或旧实验。"""

import json
import math
from dataclasses import asdict, replace
from itertools import pairwise

from braking_lesson import BRAKING_MODES
from lab_experiment import LabExperiment, LabOptions
from lab_maneuvers import path_error
from lab_records import LabRecord, changed_conditions, export_record
from player_road_ab import checked_record, document
from race import GameMode
from vehicle_designs import REFERENCE_DESIGN
from vehicle_parameters import config_from_document


def prepare_pair(a, b):
    if a is None or b is None:
        raise ValueError('请先在道路上完成或结束改装后同题，建立完整A/B。')
    a, b = checked_record(a), checked_record(b)
    if a['context']['mode'] != b['context']['mode']:
        raise ValueError('两份道路结果不是同一道题，未开始参考复测。')
    for item in (a, b):
        config_from_document(item['config'], REFERENCE_DESIGN)
    return {'A': a, 'B': b}


def trial_options(pair):
    configs = [replace(config_from_document(pair[side]['config'], REFERENCE_DESIGN),
                       tire_substeps=REFERENCE_DESIGN.tire_substeps) for side in 'AB']
    braking = GameMode(pair['A']['context']['mode']) in BRAKING_MODES
    base = (LabOptions(speed_kph=80., duration=12.) if braking else
            LabOptions(maneuver='constant_radius', speed_kph=60., radius_m=40., duration=10.))
    options = [replace(base, friction=configs[0].road_friction,
                       abs_enabled=config.braking.abs_enabled, esc_enabled=config.stability.esc_enabled)
               for config in configs]
    return tuple(configs), tuple(options)


def measured(record):
    """从完成快照复算主要指标；未正常结束时只保留观测，不给有效主指标。"""
    summary = record.metadata['summary']
    options = LabOptions(**summary['options'])
    states = record.snapshots
    initial = states[0]
    braking = options.maneuver == 'braking'
    valid = (summary['reason'] == ('stopped' if braking else 'time_limit')
             and record.metadata['source_start'] == record.metadata['source_end']
             and record.metadata['runtime_start'] == record.metadata['runtime_end'])
    distance = sum(math.dist(a.player.position, b.player.position) for a, b in pairwise(states))
    tail = [state for state in states if state.time-initial.time >= options.duration-2-1e-9]
    error = (sum(abs(path_error(options, state.player, initial.player)) for state in tail)/len(tail)
             if not braking and tail else None)
    speed_error = max((abs(math.hypot(*state.player.velocity[:2])*3.6-options.speed_kph) for state in tail), default=None)
    return {'valid': valid, 'reason': summary['reason'], 'ticks': len(states)-1,
            'primary': (distance if braking else error) if valid else None,
            'peak_beta_deg': max((abs(row['beta']) for row in record.samples if row['beta'] is not None), default=None),
            'peak_roll_deg': max(abs(state.player.roll) for state in states),
            'max_speed_error_kph': speed_error,
            'peak_yaw_radps': max(abs(row['yaw']) for row in record.samples)}


class RoadRetest:
    def __init__(self, pair):
        self.pair = prepare_pair(pair['A'], pair['B'])
        self.configs, self.options = trial_options(self.pair)
        self.records, self.partial, self.run = [], None, None
        self.status = 'ready'

    @property
    def done(self):
        return self.status == 'completed'

    def start(self):
        self.cancel()
        self.records, self.partial = [], None
        self.status = 'running'
        self.begin_trial()

    def begin_trial(self):
        index = len(self.records)
        source = self.pair['AB'[index]]
        self.run = LabExperiment(self.options[index], config=self.configs[index], parameter_metadata={
            'basis': '道路A/B保存硬件的标准参考复测；通用参考外观，不授驾驶/工坊奖牌',
            'road_record_created_at': source['created_at'], 'road_context': source['context'],
            'source_vehicle_config': source['config']})
        self.run.paused = False

    def advance(self):
        if self.status != 'running':
            return
        if self.run is None:
            self.begin_trial()
        self.run.advance()
        if self.run.done:
            self.records.append(LabRecord.from_run(self.run))
            self.run.close()
            self.run = None
            if len(self.records) == 2:
                self.status = 'completed'

    def cancel(self, status='cancelled'):
        if self.run is not None:
            self.partial = LabRecord.from_run(self.run)
            self.run.close()
            self.run = None
        if self.status == 'running':
            self.status = status

    def capture(self):
        self.cancel()
        return {'pair': document(self.pair), 'records': tuple(self.records), 'partial': self.partial, 'status': self.status}

    @classmethod
    def restore(cls, state):
        result = cls(state['pair'])
        result.records, result.partial, result.status = list(state['records']), state['partial'], state['status']
        return result

    def report(self):
        metrics = [measured(record) for record in self.records]
        comparable = (len(metrics) == 2 and all(item['valid'] for item in metrics)
                      and self.options[0] == self.options[1]
                      and self.configs[0].traction.tcs_enabled == self.configs[1].traction.tcs_enabled
                      and self.records[0].metadata['source_start'] == self.records[1].metadata['source_start']
                      and self.records[0].metadata['runtime_start'] == self.records[1].metadata['runtime_start'])
        delta = metrics[1]['primary']-metrics[0]['primary'] if comparable else None
        effective = [record.metadata['vehicle_config'] for record in self.records]
        return {'schema': 'coastal-road-reference-retest-v1', 'status': self.status,
                'road_pair': self.pair, 'options': [asdict(options) for options in self.options],
                'metrics': metrics, 'delta': delta, 'comparable': comparable,
                'changes': changed_conditions(*self.records) if len(self.records) == 2 else {},
                'effective_overrides': [{key: {'source': self.pair['AB'[i]]['config'][key], 'reference': value}
                    for key, value in config.items() if self.pair['AB'[i]]['config'][key] != value}
                    for i, config in enumerate(effective)],
                'scope': '同标准参考工况；直接控制策略，非道路键盘回放，不授奖或改当前车'}

    def export(self, folder):
        if not self.done:
            raise ValueError('两次参考试验尚未完成，未导出成完整A/B。')
        path = export_record(self.records[1], folder, baseline=self.records[0])
        (folder/'retest.json').write_text(json.dumps(self.report(), ensure_ascii=False, indent=2,
                                                    allow_nan=False), encoding='utf-8')
        return path
