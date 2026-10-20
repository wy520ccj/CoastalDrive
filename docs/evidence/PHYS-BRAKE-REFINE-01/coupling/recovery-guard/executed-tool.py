"""只诊断恢复中仍过滑的增压资格；生产控制/机械参数保持。"""

import argparse
import gzip
import hashlib
import json
import math
import sys
from dataclasses import asdict, replace
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
from vehicle_brakes import Brakes
from vehicle_state import FIXED_DT


def recovery_guard(self, requests, wheels, radius, dt):
    """候选：预测仍决定减压，实际滑移超出原目标上带时不提前增压。"""
    previous = self.states
    Brakes.advance(self, requests, wheels, radius, dt)
    states = []
    for old, state in zip(previous, self.states, strict=True):
        if state.phase == 'apply' and state.braking_slip > self.config.target_slip+self.config.slip_hysteresis:
            command = min(old.commanded, state.requested)
            pressure = (command if self.config.response_time == 0. else
                        old.pressure+(command-old.pressure)*(1-math.exp(-dt/self.config.response_time)))
            state = replace(state, commanded=command, pressure=pressure, phase='hold')
        states.append(state)
    self.states = tuple(states)
    return tuple(state.pressure for state in states)


def metrics(rows, target):
    error = locked = 0.
    premature = 0
    for row in rows[1:]:
        for i in range(4):
            wheel, brake = f'state.wheel_dynamics.{i}.', f'state.brake_states.{i}.'
            slip = row[brake+'braking_slip']
            if row[wheel+'sample_support'] and slip is not None:
                error += abs(slip-target)*FIXED_DT
                locked += (slip > .8)*FIXED_DT
                premature += row[brake+'phase'] == 'apply' and slip > target+.015
    return {'slip_error_integral': error, 'locked_wheel_seconds': locked,
            'over_slip_apply_samples': premature}


def check(output):
    output.mkdir(parents=True)
    source, runtime = model_fingerprint(), runtime_fingerprint()
    original = esc_probe._create_vehicle

    def create(config):
        world, vehicle = original(config)
        vehicle.brakes.advance = MethodType(recovery_guard, vehicle.brakes)
        return world, vehicle

    results = []
    evidence = ROOT/'docs/evidence/PHYS-BRAKE-REFINE-01'
    with patch.object(esc_probe, '_create_vehicle', create):
        for steps in (2, 4, 8, 16):
            config = replace(REFERENCE_CAR, engine_axis=(1., 0., 0.), input_shaft_axis=(1., 0., 0.),
                             downstream_axes=((1., 0., 0.),)*3, tire_substeps=steps)
            summary, rows = esc_probe.run_trial('airborne-recontact', True, 6., 'simulation', vehicle_config=config)
            baseline = json.loads(gzip.decompress((evidence/'baseline'/f'steps-{steps}.json.gz').read_bytes()))
            item = {'case': 'airborne-recontact', 'substeps': steps, 'summary': summary,
                    'metrics': metrics(rows, config.braking.target_slip),
                    'reused_baseline_metrics': metrics(baseline, config.braking.target_slip)}
            data = json.dumps(rows, allow_nan=False).encode('utf-8')
            (output/f'steps-{steps}.json.gz').write_bytes(gzip.compress(data, mtime=0))
            item['rows_sha256'] = hashlib.sha256(data).hexdigest()
            results.append(item)
            print(json.dumps({'case': item['case'], 'steps': steps, 'distance': summary['path_distance_m'],
                              'stop_s': summary['time_to_stop_s'], 'metrics': item['metrics']}), flush=True)
        nominal = json.loads((evidence/'nominal/summary.json').read_text(encoding='utf-8'))
        for case in ('asphalt-brake', 'low-mu-brake'):
            config = esc_probe.trial_config(case, True)
            previous = next(item for item in nominal['trials'] if item['case'] == case and not item['filtered'])
            assert json.loads(json.dumps(asdict(config))) == previous['summary']['config']
            summary, rows = esc_probe.run_trial(case, True, 6., 'simulation', vehicle_config=config)
            baseline = json.loads(gzip.decompress((evidence/'nominal'/f'{case}-original.json.gz').read_bytes()))
            item = {'case': case, 'summary': summary, 'metrics': metrics(rows, config.braking.target_slip),
                    'reused_baseline_summary': previous['summary'],
                    'reused_baseline_metrics': metrics(baseline, config.braking.target_slip)}
            data = json.dumps(rows, allow_nan=False).encode('utf-8')
            (output/f'{case}.json.gz').write_bytes(gzip.compress(data, mtime=0))
            item['rows_sha256'] = hashlib.sha256(data).hexdigest()
            results.append(item)
            print(json.dumps({'case': case, 'distance': summary['stopping_path_distance_m'],
                              'stop_s': summary['time_to_stop_s'], 'metrics': item['metrics'],
                              'baseline_metrics': item['reused_baseline_metrics']}), flush=True)
    differences = [abs(b['summary']['path_distance_m']-a['summary']['path_distance_m'])
                   for a, b in pairwise(results[:4])]
    stop_ticks = [round(item['summary']['time_to_stop_s']/FIXED_DT) for item in results[:4]]
    result = {'source_start': source, 'runtime_start': runtime, 'source_end': model_fingerprint(),
              'runtime_end': runtime_fingerprint(), 'trials': results, 'path_differences': differences,
              'original_path_gate': all(b < a for a, b in pairwise(differences)),
              'original_stop_gate': abs(stop_ticks[-1]-stop_ticks[-2]) <= 1,
              'diagnostic_tool_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
              'scope': '只诊断实际过滑时不预先增压，沿用原参数/预测/阈值；生产未改；旧基线明确复用'}
    assert source == result['source_end'] and runtime == result['runtime_end']
    (output/'summary.json').write_text(json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False), encoding='utf-8')
    return {'path_differences': differences, 'original_path_gate': result['original_path_gate'],
            'original_stop_gate': result['original_stop_gate']}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(check(args.output.resolve())))
