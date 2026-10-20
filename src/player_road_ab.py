"""玩家最近一次改装的完整道路A/B；不授奖、不拼接单门、不积分车辆。"""

import json
import math
from dataclasses import asdict
from datetime import UTC, datetime
from itertools import pairwise

from lap_ghost import ghost_context
from race import GameMode
from slalom_lesson import GATES, SLALOM_MODES

VERSION = 'player-slalom-ab-v1'


def context(session):
    return {'mode': session.mode.value, 'driving_mode': session.driving_mode.value,
            'input': asdict(session.driving_mode.input_config), 'world': ghost_context(session.seed)}


def document(value):
    return json.loads(json.dumps(value, ensure_ascii=False, allow_nan=False))


def checked_record(value):
    if not isinstance(value, dict) or not isinstance(value['context'], dict) or not isinstance(value['config'], dict):
        raise TypeError('道路对照记录格式无效')
    mode = GameMode(value['context']['mode'])
    if mode not in SLALOM_MODES or not isinstance(value['created_at'], str):
        raise ValueError('道路对照题目或时间无效')
    if (value['context']['driving_mode'] not in ('game', 'simulation')
            or not isinstance(value['context']['input'], dict) or not isinstance(value['context']['world'], dict)):
        raise ValueError('道路对照输入或运行条件无效')
    config, result = value['config'], value['result']
    if not isinstance(result, dict) or result['finished'] is not True or type(result['succeeded']) is not bool:
        raise ValueError('道路对照须为已结束的真实课题结果')
    if (type(result['fast']) is not bool or result['fast'] != (mode == GameMode.FAST_SLALOM)
            or type(result['gates']) is not int or not 0 <= result['gates'] <= 6):
        raise ValueError('道路对照题目/门数不一致')
    if not isinstance(result['reason'], str) or not result['reason']:
        raise ValueError('道路对照缺少结束原因')
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
    old.pop('lateral_stiffness')
    new.pop('lateral_stiffness')
    if old != new:
        reasons.append('除前胎外的硬件或路面不同')
    return reasons


class PlayerRoadAB:
    def __init__(self, path):
        self.path, self.a, self.b, self.target = path, None, None, None
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
            if value['version'] != VERSION or not isinstance(value['target'], dict):
                raise ValueError('道路对照版本或目标硬件无效')
            a = checked_record(value['A'])
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
            temporary.write_text(json.dumps({'version': VERSION, 'A': a, 'B': b, 'target': target},
                                            ensure_ascii=False, indent=2, allow_nan=False), encoding='utf-8')
            temporary.replace(self.path)
        except (OSError, ValueError) as error:
            self.notice = '道路对照未保存，旧对照保留：'+str(error)
            return False
        self.a, self.b, self.target, self.notice = a, b, target, ''
        return True

    def freeze(self, attempt, target):
        a = checked_record(attempt)
        saved = self.save(a, None, document(asdict(target)))
        self.capture_blocked = not saved
        return saved

    def observe(self, attempt):
        if (self.capture_blocked or self.a is None or attempt['context']['mode'] != self.a['context']['mode']
                or attempt['config'] != self.target):
            return False
        b = checked_record(attempt)
        return self.save(self.a, b, self.target)
