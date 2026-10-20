"""同一配方的三站巡回与完整最佳；消费原挑战结果，不改驾驶或单项成绩。"""

import json
import math
from dataclasses import asdict, dataclass

from overtake_routes import OVERTAKE_ROUTES
from race import GameMode
from sprint_routes import SPRINT_ROUTES

VERSION = 'coastal-tour-v1'
LEGS = (GameMode.VALLEY_PACE, GameMode.BEND_SPRINT, GameMode.HILL_TRAFFIC)
TITLES = ('山谷节奏', '平路连弯', '弯坡车流')
POINTS = {'铜': 1, '银': 2, '金': 3}


def medal_for(mode, seconds):
    if mode in SPRINT_ROUTES:
        return SPRINT_ROUTES[mode].medal_for(seconds)
    return next((medal for medal, target in OVERTAKE_ROUTES[mode].targets if seconds <= target), '')


@dataclass(frozen=True)
class TourEntry:
    mode: str
    seconds: float
    medal: str


def points(entries):
    return sum(POINTS[entry.medal] for entry in entries)


def overall_medal(entries):
    return ('金' if points(entries) >= 8 else '银' if points(entries) >= 6 else '铜') if len(entries) == 3 else ''


def better(candidate, previous):
    return not previous or points(candidate) > points(previous) or (
        points(candidate) == points(previous) and sum(row.seconds for row in candidate) < sum(row.seconds for row in previous))


def read_entries(rows, *, complete=False):
    if not isinstance(rows, list) or len(rows) > 3 or (complete and len(rows) != 3):
        raise ValueError('巡回站数无效')
    entries = []
    for index, row in enumerate(rows):
        if not isinstance(row, dict):
            raise TypeError('巡回记录须为对象')
        entry = TourEntry(row['mode'], row['seconds'], row['medal'])
        if (entry.mode != LEGS[index].value or type(entry.seconds) not in (int, float)
                or not math.isfinite(entry.seconds) or entry.seconds <= 0 or entry.medal not in POINTS
                or medal_for(LEGS[index], entry.seconds) != entry.medal):
            raise ValueError('巡回顺序、时间或奖牌不匹配')
        entries.append(entry)
    return tuple(entries)


class DrivingTour:
    def __init__(self, path, variant):
        self.path, self.variant = path, variant
        self.current = self.best = ()
        self.groups = {}
        self.notice = ''
        self.blocked_read = False
        self.new_best = False
        try:
            document = json.loads(path.read_text(encoding='utf-8'))
        except FileNotFoundError:
            return
        except (OSError, ValueError) as error:
            self.notice = '巡回文件未能读取，本次临时进行：'+str(error)
            self.blocked_read = True
            return
        if not isinstance(document, dict) or document.get('version') != VERSION or not isinstance(document.get('groups'), dict):
            self.notice = '巡回文件版本或格式无效，本次临时进行，原文件保留。'
            self.blocked_read = True
            return
        for key, group in document['groups'].items():
            if not isinstance(group, dict):
                self.notice = '部分巡回分组格式无效，其他配方保留。'
                continue
            try:
                current = read_entries(group['current'])
            except (ValueError, KeyError, TypeError):
                current = ()
                self.notice = '部分本轮进度无效，可用完整最佳与其他配方保留。'
            try:
                best = read_entries(group['best'], complete=True) if group['best'] else ()
            except (ValueError, KeyError, TypeError):
                best = ()
                self.notice = '部分综合最佳无效，可用本轮进度与其他配方保留。'
            self.groups[key] = {'current': [asdict(row) for row in current], 'best': [asdict(row) for row in best]}
            if key == variant:
                self.current, self.best = current, best

    def save(self, current, best):
        """文件失败保留旧最佳与原文件；已过站点仍可在本次会话中继续。"""
        groups = {**self.groups, self.variant: {'current': [asdict(row) for row in current], 'best': [asdict(row) for row in best]}}
        self.current = current
        self.new_best = False
        try:
            if self.blocked_read:
                raise ValueError('原巡回文件未能读取，请先检查存储目录；未覆盖原文件')
            self.path.parent.mkdir(parents=True, exist_ok=True)
            temporary = self.path.with_suffix('.tmp')
            temporary.write_text(json.dumps({'version': VERSION, 'groups': groups}, ensure_ascii=False, indent=2, allow_nan=False), encoding='utf-8')
            temporary.replace(self.path)
        except (OSError, ValueError) as error:
            self.notice = '巡回进度未保存，本次仍可继续：'+str(error)
            return False
        self.groups, self.best = groups, best
        self.notice = ''
        return True

    def restart(self):
        self.save((), self.best)

    def accept(self, mode, variant, highway):
        """只消费当前站的本次结果；重试失败不改变已过站点。"""
        self.new_best = False
        if variant != self.variant:
            return '硬件或输入已改变，本项不计巡回；原配方进度保留。'
        if len(self.current) == 3 or mode != LEGS[len(self.current)]:
            raise ValueError('巡回站序与本次驾驶不一致')
        result = highway.sprint if mode in SPRINT_ROUTES else highway.overtake
        if not highway.finished or not highway.succeeded or highway.collisions or result is None or not result.finished or not result.succeeded:
            return '本站未通过；已过站点保留，重试当前站。'
        if (result.route_id != mode.value or type(result.seconds) not in (int, float)
                or not math.isfinite(result.seconds) or result.seconds <= 0):
            raise ValueError('巡回结果路线或时间无效')
        medal = medal_for(mode, result.seconds)
        if not medal:
            return '本站有效完成；达到铜牌后可继续下一站。'
        entry = TourEntry(mode.value, result.seconds, medal)
        current = (*self.current, entry)
        improved = len(current) == 3 and better(current, self.best)
        best = current if improved else self.best
        saved = self.save(current, best)
        self.new_best = improved and saved
        if len(current) == 3:
            return f'三站完成 · 巡回{overall_medal(current)}牌 · {points(current)}/9分'
        return f'本站{medal}牌 · 已过{len(current)}/3站 · {points(current)}/9分'
