"""各挑战自己的工程草稿；不购买零件、不写玩家工程车辆。"""

import hashlib
import json
from dataclasses import asdict
from pathlib import Path

from challenge_build import PRICE_VERSION, BuildDraft

# 评级或裁判更新后沿用兼容的改装草稿。不同山脊路线仍用各自的草稿。
_EARLIER_RATING_RULES = {
    'budget-energy-medals-v1': ('budget-energy-v1',),
    'budget-bend-medals-v1': ('budget-bend-trial-v1', 'budget-route-v2'),
    'budget-route-v2-medals-v1': ('budget-route-v2',),
    'budget-valley-braking-v1': ('budget-route-v2-medals-v1', 'budget-route-v2'),
    'budget-route-v4-medals-v1': ('budget-route-v4',),
    'budget-route-v5-medals-v1': ('budget-route-v5',),
    'budget-distance-lanes-v1': ('budget-energy-v1',),
    'budget-overtake-finish-v1': ('budget-energy-medals-v1', 'budget-energy-v1'),
}


class ChallengePlans:
    def __init__(self, path):
        self.path = Path(path)
        self.notice = ''

    def _key(self, spec, version):
        condition = {'id': spec.id, 'base': asdict(spec.base_config), 'rules': version,
                     'allowed': spec.allowed, 'prices': PRICE_VERSION}
        return spec.id+':'+hashlib.sha256(json.dumps(condition, sort_keys=True,
                                                   allow_nan=False).encode()).hexdigest()

    def _read(self):
        try:
            data = json.loads(self.path.read_text(encoding='utf-8'))
        except FileNotFoundError:
            return {'version': 1, 'plans': {}}
        if data['version'] != 1 or not isinstance(data['plans'], dict):
            raise ValueError('挑战方案格式无效')
        return data

    def load(self, spec):
        try:
            plans = self._read()['plans']
            versions = (spec.version, *_EARLIER_RATING_RULES.get(spec.version, ()))
            row = None
            for version in versions:
                key = self._key(spec, version)
                if key in plans:
                    row = plans[key]
                    break
            draft = BuildDraft() if row is None else BuildDraft(**row)
            spec.configuration(draft)
        except (OSError, ValueError, TypeError, KeyError) as error:
            self.notice = '方案未能读取，原文件保留：'+str(error)
            return BuildDraft()
        self.notice = ''
        return draft

    def save(self, spec, draft):
        spec.configuration(draft)
        try:
            data = self._read()
            data['plans'][self._key(spec, spec.version)] = asdict(draft)
            self.path.parent.mkdir(parents=True, exist_ok=True)
            temporary = self.path.with_suffix('.tmp')
            temporary.write_text(json.dumps(data, ensure_ascii=False, allow_nan=False,
                                             indent=2)+'\n', encoding='utf-8')
            temporary.replace(self.path)
        except (OSError, ValueError, TypeError, KeyError) as error:
            self.notice = '方案未保存，原记录保留：'+str(error)
            return False
        self.notice = '本关方案已保存'
        return True
