"""保存预算内完整完赛、奖牌纪录和专项最佳。"""

import hashlib
import json
import logging
import uuid
from dataclasses import asdict
from pathlib import Path
from tempfile import TemporaryDirectory

from challenge_build import PRICE_VERSION, BuildDraft
from challenge_rules import MEDALS
from fuel import FUEL_MODEL_VERSION
from race import valid_digest

METRICS = {'fastest': 'seconds', 'economy': 'litres', 'cheapest': 'cost'}


def _digest(document):
    return hashlib.sha256(json.dumps(document, sort_keys=True, ensure_ascii=False,
                                     allow_nan=False, separators=(',', ':')).encode()).hexdigest()


class ChallengeScores:
    def __init__(self, path, spec, input_group, physics_context):
        self.path, self.spec = Path(path), spec
        self.metrics = {**METRICS, 'specialist': 'metric_value'} if spec.assessment == 'lower' else METRICS
        self.context = {'challenge': asdict(spec), 'input': input_group, 'physics': physics_context,
                        'price': PRICE_VERSION, 'fuel': FUEL_MODEL_VERSION}
        self.key = _digest(self.context)
        self.notice = ''
        self.pending_score = None
        self.pending_folder = self.path.with_name('challenge-score-pending')/self.key
        self.records = {}
        self.completed = {}
        try:
            self._read()
        except (OSError, ValueError, KeyError, TypeError) as error:
            self.notice = '挑战成绩未能读取，原文件保留：'+str(error)

    def _validate(self, record, medal=None):
        if not isinstance(record['run_id'], str) or len(record['run_id']) != 32:
            raise ValueError('挑战记录编号无效')
        build = BuildDraft(**record['build'])
        result = self.spec.evaluate(build, record['seconds'], record['litres'], metric_value=record.get('metric_value'))
        if (not result.official
                or medal is not None and (result.medal not in MEDALS
                    or MEDALS.index(result.medal) < MEDALS.index(medal))
                or record['cost'] != result.cost or record['medal'] != result.medal
                or record['config'] != _digest(asdict(self.spec.configuration(build)))):
            raise ValueError('完整驾驶记录与本关规则或车辆不一致')
        splits = record.get('splits', [])
        if splits:
            previous = (0., 0., 0.)
            for row in splits:
                values = row['distance_m'], row['seconds'], row['litres']
                if not (previous[0] < values[0] <= self.spec.distance_m
                        and previous[1] < values[1] <= result.seconds
                        and previous[2] <= values[2] <= result.litres):
                    raise ValueError('分段不是同一次连续驾驶')
                previous = values
            if self.spec.assessment == 'road' and previous != (self.spec.distance_m, result.seconds, result.litres):
                raise ValueError('最后分段与完整驾驶结果不一致')

    def _read(self):
        try:
            document = json.loads(self.path.read_text(encoding='utf-8'))
        except FileNotFoundError:
            document = {'version': 1, 'contexts': {}}
        if document['version'] != 1 or not isinstance(document['contexts'], dict):
            raise ValueError('挑战成绩格式无效')
        group = document['contexts'].get(self.key)
        records = {} if group is None else group['records']
        if not isinstance(records, dict) or set(records)-set(MEDALS):
            raise ValueError('挑战奖牌记录无效')
        if group is not None and _digest(group['context']) != self.key:
            raise ValueError('挑战条件与记录分组不一致')
        for medal, metrics in records.items():
            if not isinstance(metrics, dict) or set(metrics)-set(self.metrics):
                raise ValueError('挑战比较指标无效')
            for record in metrics.values():
                self._validate(record, medal)
        completed = {} if group is None else group.get('completed', {})
        if not isinstance(completed, dict) or set(completed)-set(self.metrics):
            raise ValueError('有效完赛比较指标无效')
        for record in completed.values():
            self._validate(record)
        # 早期文件只有奖牌记录，已有的同条件实跑也要参与个人最佳。
        completed = dict(completed)
        for name, key in METRICS.items():
            best = min((metrics[name] for metrics in records.values() if name in metrics),
                       key=lambda row: row[key], default=None)
            if best is not None and (name not in completed or best[key] < completed[name][key]):
                completed[name] = best
        if self.spec.assessment == 'lower':
            # 旧档保留过的完整驾驶仍可参加专项比较，打开存档时不改写原文件。
            known = [*completed.values(), *(row for group in records.values() for row in group.values())]
            if known:
                best = min(known, key=lambda row: row['metric_value'])
                if 'specialist' not in completed or best['metric_value'] < completed['specialist']['metric_value']:
                    completed['specialist'] = best
                records = {medal: dict(metrics) for medal, metrics in records.items()}
                for index, medal in enumerate(MEDALS):
                    best = min((row for row in known if row['medal'] in MEDALS[index:]),
                               key=lambda row: row['metric_value'], default=None)
                    if best is not None:
                        metrics = records.setdefault(medal, {})
                        if 'specialist' not in metrics or best['metric_value'] < metrics['specialist']['metric_value']:
                            metrics['specialist'] = best
        self.records, self.completed = records, completed
        return document

    @property
    def reference(self):
        return self.completed.get('specialist' if self.spec.assessment == 'lower' else 'fastest')

    def _write(self, document):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.path.with_suffix('.tmp')
        temporary.write_text(json.dumps(document, ensure_ascii=False, allow_nan=False,
                                         indent=2)+'\n', encoding='utf-8')
        temporary.replace(self.path)

    def ghost_digest(self, mode, run_id):
        best = self.completed.get('fastest')
        if best is None or mode.value != self.spec.id or best['run_id'] != run_id:
            return None
        digest = best.get('ghost')
        if digest is not None and not valid_digest(digest):
            raise ValueError('预算幽灵内容摘要无效')
        return digest

    def attach_ghost(self, mode, run_id, seconds, splits, digest):
        if not valid_digest(digest):
            raise ValueError('预算幽灵内容摘要无效')
        document = self._read()
        best = self.completed.get('fastest')
        if (best is None or mode.value != self.spec.id or best['run_id'] != run_id
                or best['seconds'] != seconds or tuple(row['seconds'] for row in best.get('splits', ())) != tuple(splits)):
            raise ValueError('最快完赛已改变，幽灵未关联')
        completed = {**self.completed, 'fastest': {**best, 'ghost': digest}}
        document['contexts'][self.key]['completed'] = completed
        self._write(document)
        self.completed = completed

    def record(self, result, *, splits=()):
        if result.challenge_id != self.spec.id or result.rules_version != self.spec.version:
            raise ValueError('挑战结果属于另一关或规则版本')
        # 不接受只改摘要的成绩；以原车、参数、燃油量和用时重新核对本次奖牌。
        expected = self.spec.evaluate(result.build, result.seconds, result.litres,
                                      valid=result.valid, metric_value=result.metric_value)
        if (result.price_version != PRICE_VERSION or result.fuel_version != FUEL_MODEL_VERSION
                or (result.medal, result.cost, result.consumption, result.official)
                != (expected.medal, expected.cost, expected.consumption, expected.official)):
            raise ValueError('挑战结果与实际方案或计量版本不一致')
        if not result.official:
            return ()
        row = {'run_id': uuid.uuid4().hex, 'build': asdict(result.build),
               'seconds': result.seconds, 'litres': result.litres,
               'cost': result.cost, 'medal': result.medal,
               'metric_value': result.metric_value,
               'config': _digest(asdict(self.spec.configuration(result.build))),
               'splits': [asdict(split) for split in splits]}
        try:
            self._validate(row, result.medal or None)
        except (ValueError, KeyError, TypeError) as error:
            self.pending_score = None
            self.notice = '挑战成绩未保存，原记录保留：'+str(error)
            return ()
        self.pending_score = row
        return self.retry_pending()

    def retry_pending(self):
        row = self.pending_score
        if row is None:
            return ()
        path = self.pending_folder/(row['run_id']+'.json')
        try:
            updated = self._commit(row)
        except (OSError, ValueError, KeyError, TypeError) as error:
            self.notice = '挑战成绩未保存，原记录保留：'+str(error)
            try:
                if not path.is_file():
                    self.pending_folder.mkdir(parents=True, exist_ok=True)
                    with TemporaryDirectory(dir=self.pending_folder) as folder:
                        temporary = Path(folder)/path.name
                        temporary.write_text(json.dumps({'context': self.key, 'record': row}, ensure_ascii=False,
                                                        allow_nan=False)+'\n', encoding='utf-8')
                        temporary.replace(path)
            except OSError as write_error:
                logging.getLogger(__name__).warning('待保存挑战成绩未写入临时存档: %s', write_error)
            return ()
        self.pending_score, self.notice = None, ''
        try:
            path.unlink(missing_ok=True)
        except OSError as error:
            logging.getLogger(__name__).warning('已处理的待保存挑战文件未清理: %s', error)
        return updated

    def recover_pending(self):
        for path in sorted(self.pending_folder.glob('*.json')):
            try:
                saved = json.loads(path.read_text(encoding='utf-8'))
                row = saved['record']
                if saved['context'] != self.key or row['run_id'] != path.stem:
                    raise ValueError('待保存挑战记录分组不符')
                self._validate(row)
            except (OSError, ValueError, KeyError, TypeError) as error:
                logging.getLogger(__name__).warning('待保存挑战记录未读取: %s', error)
                continue
            self.pending_score = row
            self.retry_pending()
            if self.pending_score is not None:
                break

    def _commit(self, row):
        document = self._read()
        records = {medal: dict(metrics) for medal, metrics in self.records.items()}
        completed = dict(self.completed)
        updated = []
        for name, key in self.metrics.items():
            if name not in completed or row[key] < completed[name][key]:
                completed[name] = row
                updated.append(('完赛', name))
        grade = row['medal']
        medals = MEDALS[:MEDALS.index(grade)+1] if grade in MEDALS else ()
        for medal in medals:
            metrics = records.setdefault(medal, {})
            for name, key in self.metrics.items():
                if name not in metrics or row[key] < metrics[name][key]:
                    metrics[name] = row
                    updated.append((medal, name))
        if updated:
            document['contexts'][self.key] = {'context': self.context, 'records': records,
                                            'completed': completed}
            self._write(document)
            self.records, self.completed = records, completed
        return tuple(updated)
