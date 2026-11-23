"""按条件保存最近两套不同方案的完整自动试车。"""

import hashlib
import json
import math
from dataclasses import asdict, dataclass, replace
from pathlib import Path
from tempfile import TemporaryDirectory

from challenge_build import PRICE_VERSION, BuildDraft
from challenge_rules import ChallengeResult
from challenge_run import EnergySplit
from fuel import FUEL_MODEL_VERSION
from race import GameMode
from slalom_lesson import GATE_HALF_WIDTH, GATES
from sprint_routes import VALLEY_BRAKING


@dataclass(frozen=True)
class ValleyTrial:
    gate_kph: float
    braking_request: float
    zone_entry_kph: float

    def __post_init__(self):
        zone = VALLEY_BRAKING.speed_zone
        values = self.gate_kph, self.braking_request, self.zone_entry_kph
        if (not all(type(value) in (int, float) and math.isfinite(value) for value in values)
                or self.gate_kph < VALLEY_BRAKING.entry_kph or not 0. <= self.braking_request <= 1.
                or not zone.minimum_kph <= self.zone_entry_kph <= zone.maximum_kph):
            raise ValueError('山谷试车制动数据无效')


@dataclass(frozen=True)
class TrialReference:
    result: ChallengeResult
    splits: tuple[EnergySplit, ...]
    clearances: tuple[float, ...] = ()
    valley: ValleyTrial | None = None


class TrialReferences:
    def __init__(self, folder):
        self.folder = Path(folder)
        self.notice = ''
        self.pending = {}

    def _path(self, group):
        context = json.dumps((group, PRICE_VERSION, FUEL_MODEL_VERSION), sort_keys=True, allow_nan=False)
        return self.folder/(hashlib.sha256(context.encode()).hexdigest()+'.json')

    @staticmethod
    def _reference(row, spec, gates):
        splits = tuple(EnergySplit(**item) for item in row['splits'])
        expected_gates = gates if spec.assessment == 'road' else gates[:len(splits)]
        if tuple(split.distance_m for split in splits) != expected_gates:
            raise ValueError('试车分段与本关门位不一致')
        seconds = litres = 0.
        for split in splits:
            if not (seconds < split.seconds and litres <= split.litres):
                raise ValueError('试车分段的用时或耗油倒退')
            seconds, litres = split.seconds, split.litres
        metric = None
        if spec.assessment != 'road':
            if not (row['seconds'] >= seconds and row['litres'] >= litres and row['metric_value'] is not None):
                raise ValueError('缺少完整专项试车数据')
            seconds, litres, metric = row['seconds'], row['litres'], row['metric_value']
        result = spec.evaluate(BuildDraft(**row['build']), seconds, litres, metric_value=metric)
        clearances = ()
        if spec.id == GameMode.FAST_SLALOM.value:
            clearances = tuple(row['clearances'])
            if len(clearances) != len(GATES) or any(
                type(value) not in (int, float) or not math.isfinite(value) or not 0. <= value <= GATE_HALF_WIDTH
                for value in clearances
            ):
                raise ValueError('高速试车须有六道有效门的车身余量')
        valley = None
        if 'valley' in row:
            if spec.id != GameMode.VALLEY_PACE.value or spec.version != VALLEY_BRAKING.version:
                raise ValueError('制动窗口数据不属于本关')
            valley = ValleyTrial(**row['valley'])
        return TrialReference(replace(result, official=False, medal='', next_target=None,
                                      notice='自动试车 · 已完成，不计成绩'), splits, clearances, valley)

    def _read(self, path, spec, gates):
        try:
            document = json.loads(path.read_text(encoding='utf-8'))
        except FileNotFoundError:
            return ()
        if document['version'] not in (1, 2) or document['group'] != path.stem:
            raise ValueError('试车记录版本或分组不匹配')
        rows = [document] if document['version'] == 1 else document['runs']
        if not isinstance(rows, list) or not 1 <= len(rows) <= 2:
            raise ValueError('试车对照记录数量无效')
        references = tuple(self._reference(row, spec, gates) for row in rows)
        if len({reference.result.build for reference in references}) != len(references):
            raise ValueError('试车对照重复保存同一方案')
        return references

    def load(self, group, spec, gates, *, build=None):
        path = self._path(group)
        self.notice = ''
        try:
            references = self.pending[path] if path in self.pending else self._read(path, spec, gates)
        except (OSError, ValueError, KeyError, TypeError) as error:
            self.notice = '试车对照未能读取：'+str(error)
            return None
        if not references:
            return None
        return next((reference for reference in references if reference.result.build != build), references[0])

    @staticmethod
    def _row(spec, result, splits, clearances, valley):
        row = {'build': asdict(result.build), 'splits': [asdict(split) for split in splits]}
        if spec.assessment != 'road':
            row.update(seconds=result.seconds, litres=result.litres, metric_value=result.metric_value)
        if spec.id == GameMode.FAST_SLALOM.value:
            row['clearances'] = clearances
        if valley is not None:
            row['valley'] = asdict(valley)
        return row

    def save(self, group, spec, gates, status, *, clearances=(), valley=None):
        path, result = self._path(group), status.result
        row = self._row(spec, result, status.splits, clearances, valley)
        reference = self._reference(row, spec, gates)
        actual = reference.result
        if (not result.valid or result.official or result.medal or
                (result.challenge_id, result.rules_version, result.seconds, result.litres, result.cost, result.metric_value)
                != (actual.challenge_id, actual.rules_version, actual.seconds, actual.litres, actual.cost,
                    actual.metric_value)):
            raise ValueError('对照须来自同条件下的一次完整自动试车')
        recent = self.pending.get(path, ())
        other = next((item for item in recent if item.result.build != result.build), None)
        try:
            # 先检查现有分组，读取失败时保留原文件，当前运行仍可继续对照。
            saved = self._read(path, spec, gates)
            if other is None:
                other = next((item for item in saved if item.result.build != result.build), None)
            references = (reference,) if other is None else (reference, other)
            document = {'version': 2, 'group': path.stem, 'runs': [
                self._row(spec, item.result, item.splits, item.clearances, item.valley) for item in references]}
            self.folder.mkdir(parents=True, exist_ok=True)
            with TemporaryDirectory(dir=self.folder) as folder:
                temporary = Path(folder)/path.name
                temporary.write_text(json.dumps(document, ensure_ascii=False, allow_nan=False)+'\n', encoding='utf-8')
                temporary.replace(path)
        except (OSError, ValueError, KeyError, TypeError) as error:
            self.pending[path] = (reference,) if other is None else (reference, other)
            self.notice = '试车对照未保存：'+str(error)
            return False
        self.pending.pop(path, None)
        self.notice = ''
        return True
