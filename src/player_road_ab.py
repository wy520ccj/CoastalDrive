"""玩家最近一次改装的完整道路A/B；不授奖、不拼接单门、不积分车辆。"""

import json
import math
from dataclasses import asdict
from datetime import UTC, datetime
from itertools import pairwise

from braking_lesson import BRAKING_MODES, medal_for
from lap_ghost import ghost_context
from race import GameMode
from short_braking import medal_for as short_medal
from slalom_lesson import GATES, SLALOM_MODES

VERSION = 'player-slalom-ab-v1'
BRAKE_VERSION = 'player-braking-ab-v1'


def context(session):
    return {'mode': session.mode.value, 'driving_mode': session.driving_mode.value,
            'input': asdict(session.driving_mode.input_config), 'world': ghost_context(session.seed)}


def document(value):
    return json.loads(json.dumps(value, ensure_ascii=False, allow_nan=False))


def checked_record(value):
    if not isinstance(value, dict) or not isinstance(value['context'], dict) or not isinstance(value['config'], dict):
        raise TypeError('道路对照记录格式无效')
    mode = GameMode(value['context']['mode'])
    if mode == GameMode.SLALOM_PRACTICE or mode not in (*SLALOM_MODES, *BRAKING_MODES) or not isinstance(value['created_at'], str):
        raise ValueError('道路对照题目或时间无效')
    if (value['context']['driving_mode'] not in ('game', 'simulation')
            or not isinstance(value['context']['input'], dict) or not isinstance(value['context']['world'], dict)):
        raise ValueError('道路对照输入或运行条件无效')
    config, result = value['config'], value['result']
    if not isinstance(result, dict) or result['finished'] is not True or type(result['succeeded']) is not bool:
        raise ValueError('道路对照须为已结束的真实课题结果')
    if not isinstance(result['reason'], str) or not result['reason']:
        raise ValueError('道路对照缺少结束原因')
    if mode in BRAKING_MODES:
        checked_braking(config, result, mode)
        return document(value)
    if (type(result['fast']) is not bool or result['fast'] != (mode == GameMode.FAST_SLALOM)
            or type(result['gates']) is not int or not 0 <= result['gates'] <= 6):
        raise ValueError('道路对照题目/门数不一致')
    times, margins = result['gate_times'], result['clearances']
    if (not isinstance(times, (list, tuple)) or not isinstance(margins, (list, tuple))
            or len(times) != len(margins) or len(times) > len(GATES)
            or result['gates'] not in (len(times), len(times)-1)):
        raise ValueError('道路对照逐门记录不完整')
    values = (*times, *margins, result['run_seconds'], config['lateral_stiffness'], config['road_friction'])
    if any(type(item) not in (int, float) or not math.isfinite(item) for item in values):
        raise ValueError('道路对照包含无效数值')
    if (result['run_seconds'] < 0 or any(t <= 0 for t in times)
            or any(b <= a for a, b in pairwise(times))
            or config['lateral_stiffness'] <= 0 or config['road_friction'] <= 0):
        raise ValueError('道路对照用时或配置无效')
    if result['succeeded'] and (result['gates'] != 6 or len(times) != 6 or min(margins) < 0 or times[-1] != result['run_seconds']):
        raise ValueError('道路对照成功结果须是完整六门')
    return document(value)


def checked_braking(config, result, mode):
    short = mode == GameMode.SHORT_BRAKING
    if type(result['short']) is not bool or result['short'] != short:
        raise ValueError('制动对照题目与指标不一致')
    values = [config['front_brake_share'], config['brake_torque'], config['road_friction'],
              result['start_progress'], result['position'], result['hold_seconds']]
    for key in ('entry_kph', 'error_m', 'stopping_m'):
        if result[key] is not None:
            values.append(result[key])
    if any(type(item) not in (int, float) or not math.isfinite(item) for item in values):
        raise ValueError('制动对照包含无效数值')
    if (not 0 <= config['front_brake_share'] <= 1 or config['brake_torque'] <= 0
            or config['road_friction'] <= 0 or result['hold_seconds'] < 0):
        raise ValueError('制动对照硬件或停稳记录无效')
    if result['succeeded']:
        entry = result['entry_kph']
        metric = result['stopping_m'] if short else result['error_m']
        if (entry is None or entry < 80 or (short and entry > 85) or metric is None
                or result['hold_seconds'] < 1-1e-9):
            raise ValueError('制动对照成功结果缺少有效测速/停稳/成绩')
        if short:
            if not 0 <= metric <= 42 or metric < max(0, result['position']-100)-1e-7:
                raise ValueError('短距对照须保留最大前进距离')
            medal = short_medal(metric)
        else:
            if abs(metric) > 10 or abs(result['position']-170-metric) > 1e-7:
                raise ValueError('定点对照须保留170米目标误差')
            medal = medal_for(abs(metric))
        if result['medal'] != medal:
            raise ValueError('制动对照奖牌与本次成绩不一致')


def record(start_context, end_context, config, result):
    if start_context != end_context:
        raise ValueError('本次驾驶的源/输入条件变化，未记录改装对照')
    return checked_record({'context': start_context, 'config': asdict(config), 'result': asdict(result),
                           'created_at': datetime.now(UTC).isoformat(timespec='seconds')})


def mismatches(a, b):
    reasons = []
    if a['context'] != b['context']:
        reasons.append('题目/种子/输入设置/模型或运行库不同')
    old, new = dict(a['config']), dict(b['config'])
    brakes = GameMode(a['context']['mode']) in BRAKING_MODES
    field = 'front_brake_share' if brakes else 'lateral_stiffness'
    old.pop(field)
    new.pop(field)
    if old != new:
        reasons.append('除制动分配外的硬件或路面不同' if brakes else '除前胎外的硬件或路面不同')
    return reasons


class PlayerRoadAB:
    def __init__(self, path, *, brakes=False):
        self.path, self.a, self.b, self.target = path, None, None, None
        self.brakes = brakes
        self.version = BRAKE_VERSION if brakes else VERSION
        self.modes = BRAKING_MODES if brakes else SLALOM_MODES
        self.notice = ''
        self.blocked = False
        self.capture_blocked = False
        try:
            value = json.loads(path.read_text(encoding='utf-8'))
        except FileNotFoundError:
            return
        except (OSError, ValueError) as error:
            self.notice = '道路对照未能读取，原文件保留：'+str(error)
            self.blocked = True
            return
        try:
            if value['version'] != self.version or not isinstance(value['target'], dict):
                raise ValueError('道路对照版本或目标硬件无效')
            a = checked_record(value['A'])
            if GameMode(a['context']['mode']) not in self.modes:
                raise ValueError('道路对照题目与存储文件不一致')
            checked_record({**a, 'config': value['target']})
            b = checked_record(value['B']) if value['B'] is not None else None
            if b is not None and (b['config'] != value['target'] or b['context']['mode'] != a['context']['mode']):
                raise ValueError('B不是本次改装的目标硬件/题目')
            self.a, self.b, self.target = a, b, document(value['target'])
        except (ValueError, TypeError, KeyError) as error:
            self.notice = '道路对照格式无效，原文件保留：'+str(error)
            self.blocked = True

    def save(self, a, b, target):
        try:
            if self.blocked:
                raise ValueError('旧对照未能读取，未覆盖原文件')
            self.path.parent.mkdir(parents=True, exist_ok=True)
            temporary = self.path.with_suffix('.tmp')
            temporary.write_text(json.dumps({'version': self.version, 'A': a, 'B': b, 'target': target},
                                            ensure_ascii=False, indent=2, allow_nan=False), encoding='utf-8')
            temporary.replace(self.path)
        except (OSError, ValueError) as error:
            self.notice = '道路对照未保存，旧对照保留：'+str(error)
            return False
        self.a, self.b, self.target, self.notice = a, b, target, ''
        return True

    def freeze(self, attempt, target):
        a = checked_record(attempt)
        if GameMode(a['context']['mode']) not in self.modes:
            raise ValueError('道路对照题目与存储文件不一致')
        saved = self.save(a, None, document(asdict(target)))
        self.capture_blocked = not saved
        return saved

    def observe(self, attempt):
        if (self.capture_blocked or self.a is None or attempt['context']['mode'] != self.a['context']['mode']
                or attempt['config'] != self.target):
            return False
        b = checked_record(attempt)
        return self.save(self.a, b, self.target)
