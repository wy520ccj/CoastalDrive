"""选车杯赛的车辆、站序和实跑奖牌线。"""

import hashlib
import json
from dataclasses import asdict, replace
from functools import lru_cache

from career_garage import CAR_BY_DESIGN
from challenge_catalog import ROAD_CHALLENGES
from challenge_rules import MEDALS, MedalTarget
from driving_modes import DrivingMode
from paths import resource_root
from race import GameMode
from vehicle_designs import vehicle_design

CUP_LEGS = (GameMode.TIME_TRIAL, GameMode.RIDGE_SPRINT, GameMode.HILL_TRAFFIC)
CUP_UNLOCK = 9
CUP_INPUT = 'game-keyboard-v32:abs-on:tcs-on:esc-on'


def cup_base_spec(design_id, mode):
    car = CAR_BY_DESIGN[design_id]
    spec = ROAD_CHALLENGES[mode]
    return replace(spec, name=spec.name+' · 综合杯', design_id=car.design_id, budget=5000,
                   targets=(), provisional=False,
                   base_config=DrivingMode.GAME.configured_vehicle(base_config=vehicle_design(design_id).config))


@lru_cache(maxsize=1)
def cup_targets():
    path = resource_root()/'assets'/'game'/'rules'/'season-cup-targets.json'
    return json.loads(path.read_text(encoding='utf-8'))


def cup_specs(design_id):
    targets = cup_targets()[design_id]
    specs = {}
    for mode in CUP_LEGS:
        spec = cup_base_spec(design_id, mode)
        row = targets[mode.value][spec.version]
        base = json.dumps(asdict(spec.base_config), sort_keys=True, separators=(',', ':'))
        if (row['rules'] != spec.version or row['shape'] != spec.road_shape
                or row['base_sha256'] != hashlib.sha256(base.encode()).hexdigest()):
            raise ValueError('杯赛奖牌线与当前赛道不一致')
        specs[mode] = replace(spec, targets=tuple(MedalTarget(medal, *target)
                              for medal, target in zip(MEDALS, row['targets'], strict=True)))
    return specs
