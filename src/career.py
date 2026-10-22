"""生涯赛事目录、星级成长和车库积分；独立保存，不迁移工程成绩。"""

import json
import math
from dataclasses import dataclass
from pathlib import Path

from career_garage import GARAGE_CARS


@dataclass(frozen=True)
class CareerEvent:
    id: str
    name: str
    chapter: int
    kind: str
    shape: str
    seed: int
    distance: float
    limit: float
    unlock: int
    reward: int
    silver: float
    gold: float
    goal: str
    tip: str
    gates: tuple = ()

    @property
    def targets(self):
        if self.kind == 'parking':
            return ('停进标记区域', '距中心不超过10米', '距中心不超过3米')
        if self.kind == 'slalom':
            return ('通过至少3道门', '通过全部5道门', f'全过5门且≤{self.gold:g}秒')
        return ('在时限内抵达终点', f'用时≤{self.silver:g}秒', f'用时≤{self.gold:g}秒')


CHAPTERS = ('初次上路', '俱乐部挑战', '海岸杯')
EVENTS = (
    CareerEvent('first-drive', '海岸初驶', 0, 'sprint', 'straight', 0, 400., 60., 0, 100, 36., 27.,
                '驶过400米终点线', '按住W起步，保持车辆在道路上。'),
    CareerEvent('parking', '稳稳停下', 0, 'parking', 'straight', 0, 200., 70., 0, 100, 10., 3.,
                '在200米停车区停稳', '先加速，看到停车区后松开W、按S刹车。'),
    CareerEvent('slalom', '穿过海风', 0, 'slalom', 'straight', 0, 420., 80., 2, 120, 0., 36.,
                '穿过至少3道宽门', '松油门控制车速，提前看下一道门；漏门可以继续。',
                ((140., -3.2), (210., 3.2), (280., -3.2), (350., 3.2), (420., 0.))),
    CareerEvent('coast-sprint', '沿海冲刺', 1, 'sprint', 'curve', 17, 800., 120., 5, 150, 65., 48.,
                '完成800米连续弯道', '弯前松油，出弯再加速。'),
    CareerEvent('ridge-run', '山脊穿行', 1, 'sprint', 'hills', 0, 1000., 150., 5, 150, 85., 64.,
                '跑完1公里起伏道路', '坡顶看远处，落坡后留出转向余量。'),
    CareerEvent('coastal-cup', '海岸杯决赛', 2, 'sprint', 'hills', 17, 1500., 180., 9, 200, 110., 90.,
                '完成1.5公里海岸杯赛段', '把加速、刹车和连续转向串起来。'),
)
EVENT_BY_ID = {event.id: event for event in EVENTS}


@dataclass(frozen=True)
class CareerPart:
    id: str
    name: str
    topic: str
    recipe: int
    price: int
    unlock: int
    description: str
    hardware: str


PARTS = (
    CareerPart('sport-front', '运动前轮', 'tires', 3, 350, 3,
               '提高前轮侧向响应，去绕桩赛试试手感。', '前轴侧偏刚度 70 kN/rad'),
    CareerPart('sport-brakes', '制动平衡套件', 'brakes', 2, 250, 5,
               '更多制动力分给前轮，去停车赛练习刹车。', '前轴制动份额 70%'),
    CareerPart('street-power', '街道动力套件', 'power', 0, 450, 8,
               '扭矩提升12%，去沿海冲刺感受加速变化。', '整条扭矩曲线 ×1.12'),
    CareerPart('sport-suspension', '运动悬架', 'suspension', 0, 400, 12,
               '弹簧更硬，阻尼同步调整；去山脊赛感受车身响应。', '弹簧刚度 +15% / 阻尼同步匹配'),
)
PART_BY_ID = {part.id: part for part in PARTS}


class CareerProgress:
    def __init__(self, path):
        self.path = Path(path)
        self.records, self.owned, self.credits = {}, set(), 0
        self.notice, self.blocked = '', False
        try:
            data = json.loads(self.path.read_text(encoding='utf-8'))
            if (data['version'] != 1 or type(data['credits']) is not int or data['credits'] < 0
                    or not isinstance(data['records'], dict) or not isinstance(data['owned'], list)
                    or any(part not in PART_BY_ID for part in data['owned'])):
                raise ValueError('生涯文件格式无效')
            for key, record in data['records'].items():
                if (key not in EVENT_BY_ID or type(record['stars']) is not int or not 1 <= record['stars'] <= 3
                        or type(record['seconds']) not in (int, float) or not math.isfinite(record['seconds'])
                        or not 0 < record['seconds'] <= EVENT_BY_ID[key].limit):
                    raise ValueError('生涯成绩无效')
            self.records, self.owned, self.credits = data['records'], set(data['owned']), data['credits']
        except FileNotFoundError:
            pass
        except (OSError, ValueError, KeyError, TypeError) as error:
            self.notice, self.blocked = '生涯存档未读取，原文件已保留：'+str(error), True

    @property
    def stars(self):
        return sum(record['stars'] for record in self.records.values())

    def available(self, event):
        return self.stars >= event.unlock

    def recommended(self):
        return next((event for event in EVENTS if self.available(event) and event.id not in self.records),
                    min((event for event in EVENTS if self.available(event)),
                        key=lambda event: self.records.get(event.id, {'stars': 0})['stars']))

    def save(self, records, owned, credits):
        try:
            if self.blocked:
                raise ValueError('原生涯文件未能读取，未覆盖原文件')
            self.path.parent.mkdir(parents=True, exist_ok=True)
            temporary = self.path.with_suffix('.tmp')
            temporary.write_text(json.dumps({'version': 1, 'records': records, 'owned': sorted(owned),
                                             'credits': credits}, ensure_ascii=False, indent=2, allow_nan=False),
                                 encoding='utf-8')
            temporary.replace(self.path)
        except (OSError, ValueError) as error:
            self.notice = '生涯进度未保存：'+str(error)
            return False
        self.records, self.owned, self.credits, self.notice = records, owned, credits, ''
        return True

    def record(self, result):
        event = EVENT_BY_ID[result.event_id]
        if not result.finished or not result.succeeded or not 1 <= result.stars <= 3 or not self.available(event):
            return {'credits': 0, 'unlocked': (), 'vehicles': (), 'saved': True}
        old = self.records.get(event.id)
        delta = max(0, result.stars-(old['stars'] if old is not None else 0))
        reward = delta*event.reward
        records = dict(self.records)
        if old is None or (result.stars, -result.elapsed) > (old['stars'], -old['seconds']):
            records[event.id] = {'stars': result.stars, 'seconds': result.elapsed}
        before = self.stars
        saved = self.save(records, set(self.owned), self.credits+reward)
        unlocked = tuple(item.name for item in EVENTS if before < item.unlock <= self.stars)
        unlocked += tuple('零件：'+part.name for part in PARTS if before < part.unlock <= self.stars)
        vehicles = tuple(car.design_id for car in GARAGE_CARS if before < car.unlock <= self.stars)
        unlocked += tuple('新车：'+car.name for car in GARAGE_CARS if car.design_id in vehicles)
        return {'credits': reward if saved else 0, 'unlocked': unlocked, 'vehicles': vehicles, 'saved': saved}

    def buy(self, part):
        if part.id in self.owned:
            return True
        if self.stars < part.unlock or self.credits < part.price:
            self.notice = '星级或积分不足，先完成其他赛事。'
            return False
        return self.save(dict(self.records), self.owned | {part.id}, self.credits-part.price)
