"""生涯赛事板展示的专项赛，沿用独立挑战的路线和成绩。"""

from dataclasses import dataclass

from career import EVENT_BY_ID
from challenge_catalog import ROAD_CHALLENGES, course_shape
from challenge_rules import MEDALS
from challenge_scores import ChallengeScores
from lap_ghost import ghost_context, record_context
from overtake_routes import OVERTAKE_ROUTES
from race import GameMode
from sprint_routes import VALLEY_BRAKING


@dataclass(frozen=True)
class ClubEvent:
    id: GameMode
    seed: int
    photo: str
    goal: str
    tip: str
    rules: str

    chapter = 1
    unlock = 5

    @property
    def name(self):
        return ROAD_CHALLENGES[self.id].name

    @property
    def distance(self):
        return ROAD_CHALLENGES[self.id].distance_m

    @property
    def shape(self):
        return course_shape(self.id)

    def best(self, session):
        group = session.driving_mode.score_variant(session.abs_enabled, session.tcs_enabled, session.esc_enabled)
        scores = ChallengeScores(session.race.scores.path.with_name('challenge-best.json'),
                                 ROAD_CHALLENGES[self.id], group, record_context(ghost_context(self.seed), self.id))
        for medal in reversed(MEDALS):
            best = scores.records.get(medal, {}).get('fastest')
            if best is not None:
                return best
        return scores.reference


_TRAFFIC = OVERTAKE_ROUTES[GameMode.HILL_TRAFFIC]
_VALLEY = VALLEY_BRAKING
_LIMIT = _VALLEY.speed_zone
CLUB_EVENTS = {
    GameMode.VALLEY_PACE: ClubEvent(GameMode.VALLEY_PACE, _VALLEY.seed, 'chase-valley.png',
        '按测速和限速要求驶过山谷', '过测速门后立即制动，出限速带再加速。',
        f'{_VALLEY.gates[0]:g} 米测速 ≥ {_VALLEY.entry_kph:g} km/h\n'
        f'{_LIMIT.start:g}–{_LIMIT.end:g} 米限速 {_LIMIT.minimum_kph:g}–{_LIMIT.maximum_kph:g} km/h'),
    GameMode.HILL_TRAFFIC: ClubEvent(GameMode.HILL_TRAFFIC, _TRAFFIC.seed, 'hill-traffic.png',
        f'安全超越{_TRAFFIC.passes}辆并驶至终点', '超过车辆后，整车领先至少10米再切回。',
        f'{_TRAFFIC.seconds:g}秒内完赛\n并行侧距≥1米，前后净距≥10米'),
}
BOARD_EVENTS = {**EVENT_BY_ID, **CLUB_EVENTS}
