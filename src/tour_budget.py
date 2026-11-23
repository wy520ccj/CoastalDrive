"""三站独立预算巡回；每份综合纪录始终保留完整一轮。"""

import hashlib
import json
import uuid
from dataclasses import asdict, dataclass

from challenge_build import PRICE_VERSION, BuildDraft
from challenge_catalog import ROAD_CHALLENGES
from driving_tour import LEGS, POINTS
from fuel import FUEL_MODEL_VERSION

VERSION = 'budget-tour-v1'
METRICS = {'fastest': 'seconds', 'economy': 'litres', 'cheapest': 'cost'}


@dataclass(frozen=True)
class TourRun:
    mode: str
    seconds: float
    litres: float
    cost: int
    medal: str
    build: BuildDraft
    run_id: str
    trace_path: str = ''


def tour_is_ranked():
    return all(ROAD_CHALLENGES[mode].targets and not ROAD_CHALLENGES[mode].provisional for mode in LEGS)


def tour_points(entries, *, ranked=None):
    ranked = tour_is_ranked() if ranked is None else ranked
    return sum(POINTS.get(entry.medal, 0) for entry in entries) if ranked else 0


def tour_medal(entries, *, ranked=None):
    if len(entries) != 3 or any(not entry.medal for entry in entries):
        return ''
    score = tour_points(entries, ranked=ranked)
    return '金' if score >= 8 else '银' if score >= 6 else '铜' if score else ''


def total(entries, field):
    return sum(getattr(entry, field) for entry in entries)


def read_tour(path):
    try:
        document = json.loads(path.read_text(encoding='utf-8'))
    except FileNotFoundError:
        return {'version': VERSION, 'groups': {}}
    if document['version'] != VERSION or not isinstance(document['groups'], dict):
        raise ValueError('预算巡回格式无效')
    return document


class BudgetTour:
    def __init__(self, path, input_group, physics, *, specs=None):
        self.path, self.variant = path, input_group
        self.cup = specs is not None
        self.specs = {mode: ROAD_CHALLENGES[mode] for mode in LEGS} if specs is None else specs
        self.legs = tuple(self.specs)
        self.ranked = all(spec.targets and not spec.provisional for spec in self.specs.values())
        self.context = {'rules': [asdict(spec) for spec in self.specs.values()],
                        'input': input_group, 'physics': physics, 'price': PRICE_VERSION, 'fuel': FUEL_MODEL_VERSION}
        self.context = json.loads(json.dumps(self.context))
        self.key = hashlib.sha256(json.dumps(self.context, sort_keys=True).encode()).hexdigest()
        self.current = self.latest = ()
        self.bests, self.groups = {}, {}
        self.notice, self.new_best, self.unsaved, self.blocked = '', False, False, False
        try:
            document = self.read()
            self.groups = document['groups']
            group = self.groups.get(self.key)
            if group is not None:
                if group['context'] != self.context:
                    raise ValueError('巡回条件与记录不一致')
                self.current = self.entries(group['current'])
                self.latest = self.entries(group['latest'], complete=True) if group['latest'] else ()
                self.bests = {name: self.entries(rows, complete=True, graded=True)
                              for name, rows in group['bests'].items()}
                if set(self.bests)-set(METRICS):
                    raise ValueError('未知综合纪录类别')
        except (OSError, ValueError, TypeError, KeyError) as error:
            self.current = self.latest = ()
            self.bests = {}
            self.blocked = True
            self.notice = '预算巡回未能读取，原文件保留：'+str(error)

    def read(self):
        return read_tour(self.path)

    def entries(self, rows, *, complete=False, graded=False):
        if not isinstance(rows, list) or len(rows) > 3 or complete and len(rows) != 3:
            raise ValueError('预算巡回须保留连续站序')
        entries = []
        for index, row in enumerate(rows):
            entry = TourRun(**{**row, 'build': BuildDraft(**row['build'])})
            mode = self.legs[index]
            spec = self.specs[mode]
            expected = spec.evaluate(entry.build, entry.seconds, entry.litres)
            if (entry.mode != mode.value or not expected.official or entry.cost != expected.cost
                    or entry.medal != expected.medal or graded and not entry.medal
                    or not isinstance(entry.run_id, str) or len(entry.run_id) != 32):
                raise ValueError('巡回记录的原车、预算或联合评价不匹配')
            entries.append(entry)
        return tuple(entries)

    @property
    def best(self):
        return self.bests.get('fastest', ())

    def _write(self, current):
        if self.blocked:
            raise ValueError('原记录未能读取，未覆盖原文件')
        document = self.read()
        document['groups'][self.key] = {'context': self.context,
            'current': [asdict(row) for row in current], 'latest': [asdict(row) for row in self.latest],
            'bests': {key: [asdict(row) for row in rows] for key, rows in self.bests.items()}}
        if self.cup:
            document.setdefault('active', {})[self.variant] = self.key
            if len(current) == len(self.legs):
                document.setdefault('completed', {})[self.variant] = self.key
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.path.with_suffix('.tmp')
        temporary.write_text(json.dumps(document, ensure_ascii=False, allow_nan=False, indent=2)+'\n', encoding='utf-8')
        temporary.replace(self.path)
        return document['groups']

    def save(self):
        self.unsaved = True
        try:
            self.groups = self._write(self.current)
        except (OSError, ValueError, TypeError, KeyError) as error:
            self.notice = '巡回进度未保存，本次仍可继续：'+str(error)
            self.new_best = False
            return False
        self.notice, self.unsaved = '', False
        return True

    def restart(self):
        try:
            self.groups = self._write(())
        except (OSError, ValueError, TypeError, KeyError) as error:
            self.notice = '未能重开巡回，原进度保留：'+str(error)
            return False
        self.current, self.new_best, self.unsaved, self.notice = (), False, False, ''
        return True

    def accept(self, mode, input_group, physics, highway, *, vehicle_config=None):
        self.new_best = False
        if input_group != self.variant or physics != self.context['physics']:
            return '输入或运行条件改变，本站未计巡回；原进度保留。'
        if len(self.current) == 3 or mode != self.legs[len(self.current)]:
            raise ValueError('巡回站序与本次驾驶不一致')
        status = highway.engineering
        if not highway.finished or not highway.succeeded or highway.collisions or status is None or status.result is None:
            return '本站未通过；重试当前站。'
        result, spec = status.result, self.specs[mode]
        if self.cup and vehicle_config != spec.configuration(result.build):
            return '参赛车辆与本轮不一致，本站未计分。'
        expected = spec.evaluate(result.build, result.seconds, result.litres, valid=result.valid)
        if (result.challenge_id != spec.id or result.rules_version != spec.version
                or result.price_version != PRICE_VERSION or result.fuel_version != FUEL_MODEL_VERSION
                or (result.cost, result.consumption) != (expected.cost, expected.consumption)):
            raise ValueError('巡回结果与本关预算或联合规则不一致')
        if not result.official or not expected.official:
            return '本站未计巡回；须有效完成、预算内且亲自驾驶。'
        if result.medal != expected.medal:
            raise ValueError('巡回奖牌与本次联合评价不一致')
        if spec.targets and not result.medal:
            return '本站未达试行铜牌，重试本站。' if spec.provisional else '本站未达铜牌，重试本站。'
        entry = TourRun(mode.value, result.seconds, result.litres, result.cost, result.medal,
                        result.build, uuid.uuid4().hex, status.trace_path)
        self.current = (*self.current, entry)
        improved = False
        if len(self.current) == 3:
            self.latest = self.current
            if tour_medal(self.current, ranked=self.ranked):
                for name, field in METRICS.items():
                    old = self.bests.get(name, ())
                    score = tour_points(self.current, ranked=self.ranked)
                    old_score = tour_points(old, ranked=self.ranked)
                    if score > old_score or score == old_score and (not old or total(self.current, field) < total(old, field)):
                        self.bests[name], improved = self.current, True
        saved = self.save()
        self.new_best = saved and improved
        if len(self.current) == 3:
            medal = tour_medal(self.current, ranked=self.ranked)
            name = '综合杯' if self.cup else '巡回'
            return f'三站完成 · {name}{medal}牌' if medal else '三站试跑完成 · 暂不授奖'
        return f'已完成{len(self.current)}/3站 · 可继续下一站'
