"""原落地制动四组细化的逐拍证据；保持原配置、初始化与六秒命令。"""

import argparse
import gzip
import hashlib
import json
import math
import sys
from dataclasses import replace
from itertools import pairwise
from pathlib import Path
from types import MethodType
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT/'src'), str(ROOT/'tools')]

from physics import esc_probe

from driving_modes import REFERENCE_CAR
from lab_records import model_fingerprint
from lab_runtime import runtime_fingerprint
from vehicle_brakes import BrakeState
from vehicle_state import FIXED_DT


def filtered_advance(self, requests, wheels, radius, dt):
    """诊断候选：限带滑移趋势，时间尺度沿用原液压响应，不写机械状态。"""
    config = self.config
    states = []
    for requested, wheel, previous in zip(requests, wheels, self.states, strict=True):
        wheel_radius = radius if wheel.rolling_radius is None else wheel.rolling_radius
        speed = abs(wheel.longitudinal_speed)
        supported = wheel.sample_support and speed >= config.minimum_speed
        slip = ((speed-math.copysign(1., wheel.longitudinal_speed)*wheel_radius*wheel.omega)/speed
                if supported else None)
        predicted = slip
        if slip is not None and previous.braking_slip is not None and config.response_time > 0:
            old_rate = ((previous.predicted_slip-previous.braking_slip)/config.response_time
                        if previous.predicted_slip is not None else 0.)
            blend = 1-math.exp(-dt/config.response_time)
            rate = old_rate+blend*((slip-previous.braking_slip)/dt-old_rate)
            predicted += config.response_time*rate
        active = (config.abs_enabled and requested > 0 and supported
                  and (previous.abs_active or predicted > config.target_slip+config.slip_hysteresis))
        command, phase = requested, 'normal'
        if active:
            command = min(previous.commanded, requested)
            error = config.target_slip-predicted
            if error < -config.slip_hysteresis:
                command = max(0., command+max(-config.release_rate, config.slip_rate_gain*error)*dt)
                phase = 'release'
            elif error > config.slip_hysteresis:
                command = min(requested, command+min(config.apply_rate, config.slip_rate_gain*error)*dt)
                phase = 'apply'
        pressure = (command if config.response_time == 0 else
                    previous.pressure+(command-previous.pressure)*(1-math.exp(-dt/config.response_time)))
        states.append(BrakeState(requested, command, pressure, slip, active, phase, wheel.sample_tick, predicted))
    self.states = tuple(states)
    return tuple(state.pressure for state in states)


def trial(config, filtered, case='airborne-recontact'):
    original = esc_probe._create_vehicle

    def create(config):
        world, vehicle = original(config)
        vehicle.brakes.advance = MethodType(filtered_advance, vehicle.brakes)
        return world, vehicle

    if filtered:
        with patch.object(esc_probe, '_create_vehicle', create):
            return esc_probe.run_trial(case, True, 6., 'simulation', vehicle_config=config)
    return esc_probe.run_trial(case, True, 6., 'simulation', vehicle_config=config)


def check(output, substeps, *, abs_disabled=False, filtered=False):
    output.mkdir(parents=True)
    source, runtime = model_fingerprint(), runtime_fingerprint()
    trials = []
    for steps in substeps:
        config = replace(REFERENCE_CAR, engine_axis=(1., 0., 0.), input_shaft_axis=(1., 0., 0.),
                         downstream_axes=((1., 0., 0.),)*3, tire_substeps=steps)
        if abs_disabled:
            config = replace(config, braking=replace(config.braking, abs_enabled=False))
        summary, rows = trial(config, filtered)
        events = []
        for previous, row in pairwise(rows):
            old = tuple(previous[f'state.wheel_dynamics.{i}.sample_support'] for i in range(4))
            new = tuple(row[f'state.wheel_dynamics.{i}.sample_support'] for i in range(4))
            if old != new:
                events.append({'time': row['time_s'], 'support': new, 'pitch': row['state.pitch'],
                    'height': row['state.position.2'], 'speed': row['horizontal_speed_mps'],
                    'pressures': [row[f'state.brake_states.{i}.pressure'] for i in range(4)]})
        data = json.dumps(rows, ensure_ascii=False, allow_nan=False).encode('utf-8')
        (output/f'steps-{steps}.json.gz').write_bytes(gzip.compress(data, mtime=0))
        trials.append({'substeps': steps, 'summary': summary, 'support_events': events,
                       'rows_sha256': hashlib.sha256(data).hexdigest()})
        print(json.dumps({'substeps': steps, 'distance': summary['path_distance_m'],
                          'stop_s': summary['time_to_stop_s'], 'support_events': events}, ensure_ascii=False), flush=True)
    differences = [abs(b['summary']['path_distance_m']-a['summary']['path_distance_m']) for a, b in pairwise(trials)]
    stop_ticks = [round(item['summary']['time_to_stop_s']/FIXED_DT) for item in trials]
    result = {'source_start': source, 'runtime_start': runtime, 'source_end': model_fingerprint(),
              'runtime_end': runtime_fingerprint(), 'trials': trials, 'path_differences': differences,
              'original_path_gate': all(b < a for a, b in pairwise(differences)),
              'original_stop_gate': abs(stop_ticks[-1]-stop_ticks[-2]) <= 1,
              'diagnostic_abs_disabled': abs_disabled,
              'diagnostic_filtered_predictor': filtered,
              'diagnostic_tool_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
              'scope': '原单一工况及原数值标准；诊断变体单列，不算原工况通过；无生产参数/阈值/物理源码修改'}
    assert result['source_end'] == source and result['runtime_end'] == runtime
    (output/'summary.json').write_text(json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False), encoding='utf-8')
    return {key: result[key] for key in ('path_differences', 'original_path_gate', 'original_stop_gate',
                                        'diagnostic_abs_disabled', 'diagnostic_filtered_predictor')}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--substeps', type=int, nargs='+', default=(2, 4, 8, 16))
    variant = parser.add_mutually_exclusive_group()
    variant.add_argument('--abs-disabled', action='store_true', help='仅诊断关闭ABS的同场景；不替代原工况验收')
    variant.add_argument('--filtered-predictor', action='store_true', help='仅诊断限带滑移预测；未接入生产')
    args = parser.parse_args()
    print(json.dumps(check(args.output.resolve(), args.substeps, abs_disabled=args.abs_disabled,
                           filtered=args.filtered_predictor), ensure_ascii=False))
