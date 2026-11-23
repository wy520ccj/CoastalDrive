"""把道路判定与权威燃油快照接成同一次挑战；不自行判断碰撞或推进车辆。"""

from dataclasses import dataclass, replace

from challenge_build import BuildDraft
from challenge_rules import MEDALS, ChallengeResult, EnergyWindow, MedalTarget
from fuel import FUEL_MODEL_VERSION
from sector_chase import ChaseCourse


@dataclass(frozen=True)
class EnergySplit:
    distance_m: float
    seconds: float
    litres: float


@dataclass(frozen=True)
class ChallengeStatus:
    challenge_id: str
    name: str
    budget: int
    cost: int
    seconds: float
    progress_m: float
    litres: float | None
    consumption: float | None
    splits: tuple[EnergySplit, ...]
    result: ChallengeResult | None = None
    save_notice: str = ''
    targets: tuple[MedalTarget, ...] = ()
    distance_m: float = 0.
    gate_count: int = 4
    reference_splits: tuple[EnergySplit, ...] = ()
    trace_path: str = ''
    assessment: str = 'road'
    reference_result: ChallengeResult | None = None
    provisional: bool = False
    record_updates: tuple[tuple[str, str], ...] = ()
    reference_label: str = ''
    score_pending: bool = False
    chase: ChaseCourse | None = None
    practice_sector: int | None = None
    chase_best: float | None = None


class ChallengeRun:
    def __init__(self, spec, build, fuel, *, gates, scores=None, trace=None, chase=None, practice_sector=None):
        spec.configuration(build)
        if not gates or gates[-1] != spec.distance_m or any(a >= b for a, b in zip((0., *gates), gates)):
            raise ValueError('挑战分段门序与规定终点不一致')
        self.spec, self.build, self.gates, self.scores = spec, build, gates, scores
        self.chase, self.practice_sector = chase, practice_sector
        self.trace = trace
        self.player_driven = True
        self.cost = build.cost
        self.window = None if fuel is None else EnergyWindow(fuel.litres, spec.distance_m)
        if fuel is not None and fuel.model != FUEL_MODEL_VERSION:
            raise ValueError('燃油观测与本关模型版本不一致')
        self.seconds = self.progress = 0.
        self.splits = ()
        self.result = None
        self.save_notice = ''
        self.record_updates = ()
        self.score_pending = False
        self.graded_references = ({grade: tuple(rows.values()) for grade, rows in scores.records.items()}
                                  if scores is not None and spec.assessment == 'road' and spec.targets else {})
        self._set_reference(None if scores is None else scores.reference)
        if chase is not None:
            if tuple(row[0] for row in chase.reference) != gates:
                raise ValueError('追时参考与当前赛道门位不一致')
            self.reference_splits = tuple(EnergySplit(*row) for row in chase.reference)
            self.reference_label = '追时参考'
            self.reference_result = None

    def _set_reference(self, reference, label=''):
        self.reference_label = label
        self.reference_splits = (() if reference is None else
                                 tuple(EnergySplit(**row) for row in reference.get('splits', ())))
        self.reference_result = (None if reference is None else
            self.spec.evaluate(BuildDraft(**reference['build']), reference['seconds'], reference['litres'],
                               metric_value=reference.get('metric_value')))

    def _set_promotion_reference(self):
        target = self.result.next_target
        if self.chase is not None or target is None or not self.graded_references:
            return
        seconds_gap, oil_gap = self.result.gaps
        # 按相对奖牌门槛的差距选择对照。只使用发车时已达该档的完整成绩。
        economy = oil_gap/target.consumption > seconds_gap/target.seconds
        field, name = ('litres', '最省油') if economy else ('seconds', '最快')
        grades = MEDALS[MEDALS.index(target.medal):]
        reference = min((row for grade in grades for row in self.graded_references.get(grade, ())),
                        key=lambda row: row[field], default=None)
        if reference is not None:
            self._set_reference(reference, target.medal+'牌'+name)

    def sample(self, fuel, progress, seconds, *, passed, finished=False, succeeded=False, reason='', metric_value=None,
               crossing_times=None):
        if self.result is not None:
            return
        if seconds < self.seconds:
            raise ValueError('挑战计时倒退，不能拼接不同次驾驶')
        if not len(self.splits) <= passed <= len(self.gates):
            raise ValueError('道路分段门序倒退或越界')
        if crossing_times is not None and len(crossing_times) != passed:
            raise ValueError('环路门线时刻与通过状态不一致')
        if self.window is not None:
            if fuel is None or fuel.model != FUEL_MODEL_VERSION:
                raise ValueError('挑战途中燃油观测中断或版本改变')
            before_fuel = self.window.previous_litres
            before_progress, before_seconds = self.progress, self.seconds
            if fuel.litres < before_fuel:
                raise ValueError('燃油累计值倒退，须结束本次挑战')
            while len(self.splits) < passed:
                gate = self.gates[len(self.splits)]
                if crossing_times is None:
                    if not before_progress < gate <= progress:
                        raise ValueError('道路通过状态与真实赛段进度不一致')
                    fraction = (gate-before_progress)/(progress-before_progress)
                else:
                    crossing = crossing_times[len(self.splits)]
                    if not before_seconds <= crossing <= seconds or seconds == before_seconds:
                        raise ValueError('环路门线不在本次真实完成步内')
                    fraction = (crossing-before_seconds)/(seconds-before_seconds)
                time = before_seconds+(seconds-before_seconds)*fraction
                litres = before_fuel+(fuel.litres-before_fuel)*fraction-self.window.start_litres
                self.splits += (EnergySplit(gate, time, litres),)
            fraction = None
            if finished and succeeded and self.spec.assessment == 'road':
                if passed != len(self.gates):
                    raise ValueError('完成挑战前须通过全部分段')
                fraction = ((self.spec.distance_m-before_progress)/(progress-before_progress)
                            if crossing_times is None else
                            (crossing_times[-1]-before_seconds)/(seconds-before_seconds))
            self.window.sample(fuel.litres, progress, finish_fraction=fraction)
        self.progress, self.seconds = progress, seconds
        if finished:
            final_time = (crossing_times[-1] if succeeded and crossing_times else
                          self.splits[-1].seconds if succeeded and self.splits and self.spec.assessment == 'road' else seconds)
            self.stop(reason, succeeded=succeeded, seconds=final_time, metric_value=metric_value)

    def stop(self, reason, *, succeeded=False, seconds=None, metric_value=None):
        if self.result is not None:
            return
        self.result = self.spec.evaluate(self.build, self.seconds if seconds is None else seconds,
                                         None if self.window is None else self.window.litres,
                                         valid=succeeded, reason=reason, metric_value=metric_value)
        if not self.player_driven:
            notice = '已完成，不计成绩' if self.result.valid else self.result.notice
            self.result = replace(self.result, official=False, medal='', next_target=None,
                                  notice='自动试车 · '+notice)
        if self.practice_sector is not None:
            self.result = replace(self.result, official=False, medal='', next_target=None, notice=reason)
        if self.scores is not None and self.player_driven:
            self._set_promotion_reference()
            self.record_updates = self.scores.record(self.result, splits=self.splits)
            self.score_pending = self.result.official and self.scores.pending_score is not None
            self._update_save_notice()

    def retry_score(self):
        if self.score_pending:
            self.record_updates = self.scores.retry_pending()
            self.score_pending = self.scores.pending_score is not None
            self._update_save_notice()

    def _update_save_notice(self):
        self.save_notice = ' · '.join(value for value in
            ('' if self.scores is None else self.scores.notice,
             '' if self.trace is None else self.trace.notice) if value)

    def save_trace(self, context):
        if self.trace is not None and self.result is not None:
            self.trace.save(self.result, self.splits, context)
            self._update_save_notice()

    @property
    def snapshot(self):
        best = None
        if self.chase is not None and self.scores is not None and self.scores.reference is not None:
            best = self.scores.reference['seconds']
        name = self.spec.name if self.chase is None else self.chase.name
        return ChallengeStatus(self.spec.id, name, self.spec.budget, self.cost,
            self.result.seconds if self.result is not None else self.seconds,
            min(self.spec.distance_m, max(0., self.progress)),
            None if self.window is None else self.window.litres,
            None if self.window is None else self.window.consumption,
            self.splits, self.result, self.save_notice, self.spec.targets, self.spec.distance_m,
            len(self.gates), self.reference_splits,
            '' if self.trace is None or self.trace.path is None else str(self.trace.path), self.spec.assessment,
            self.reference_result, self.spec.provisional, self.record_updates, self.reference_label,
            self.score_pending, self.chase, self.practice_sector, best)
