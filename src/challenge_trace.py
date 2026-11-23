"""保存正式发车后的真实完成步与输入，供能耗复算和人工难度标定。"""

import json
import uuid
from dataclasses import asdict

from challenge_build import PRICE_VERSION
from fuel import FUEL_MODEL_VERSION, FUEL_STEP_COLUMNS

TRACE_COLUMNS = ('tick', 'time', 'progress_m', 'total_litres', 'rate_lph', 'rpm', 'gear',
                 'engine_work_j', 'actual_throttle', 'steering', 'throttle', 'brake', 'direction')


class ChallengeTrace:
    def __init__(self, folder, spec, build, initial, context, controller, input_group, *, circuit=False):
        self.folder, self.spec, self.build = folder, spec, build
        self.context, self.controller = context, controller
        self.input_group = input_group
        self.initial_time = initial.time
        fuel = initial.player.powertrain_state.fuel
        self.start_litres = fuel.litres
        self.initial_tick = initial.tick
        self.rows = [(initial.tick, 0., 0., fuel.litres, fuel.rate_lph, initial.player.rpm,
                      initial.player.gear, 0., initial.player.throttle, 0., 0., 0., 1)]
        self.notice, self.path = '', None
        self.closed = False
        self.fuel_steps = [()]
        self.run_id = uuid.uuid4().hex
        self.circuit_frames = ([(*initial.player.position, initial.player.speed)] if circuit else None)

    def append(self, state, control, progress, fuel_steps=()):
        if self.closed:
            return
        if state.tick != self.rows[-1][0]+1:
            raise ValueError('挑战记录须保留连续的120Hz真实完成步')
        train, fuel = state.player.powertrain_state, state.player.powertrain_state.fuel
        self.rows.append((state.tick, state.time-self.initial_time, progress, fuel.litres,
                          fuel.rate_lph, state.player.rpm, state.player.gear, train.engine_work,
                          train.throttle, control.steering, control.throttle, control.brake, control.direction))
        self.fuel_steps.append(tuple(fuel_steps))
        if self.circuit_frames is not None:
            self.circuit_frames.append((*state.player.position, state.player.speed))

    def save(self, result, splits, end_context):
        if self.path is not None:
            return
        self.closed = True
        data = {'version': 2, 'run_id': self.run_id, 'spec': asdict(self.spec), 'build': asdict(self.build),
                'price_version': PRICE_VERSION, 'fuel_version': FUEL_MODEL_VERSION,
                'source_start': self.context, 'source_end': end_context,
                'controller': self.controller, 'physics_hz': 120,
                'input_group': self.input_group,
                'start_litres': self.start_litres, 'initial_tick': self.initial_tick,
                'result': asdict(result), 'splits': [asdict(split) for split in splits],
                'columns': TRACE_COLUMNS, 'samples': self.rows,
                'fuel_step_columns': FUEL_STEP_COLUMNS, 'fuel_steps': self.fuel_steps}
        if self.circuit_frames is not None:
            data['version'] = 3
            data['circuit_frames'] = self.circuit_frames
        try:
            self.folder.mkdir(parents=True, exist_ok=True)
            path = self.folder/(self.spec.id+'-'+self.run_id+'.json')
            temporary = path.with_suffix('.tmp')
            temporary.write_text(json.dumps(data, ensure_ascii=False, allow_nan=False,
                                             separators=(',', ':'))+'\n', encoding='utf-8')
            temporary.replace(path)
        except (OSError, ValueError) as error:
            self.notice = '试跑记录未保存：'+str(error)
            return
        self.path = path
        self.notice = ''
