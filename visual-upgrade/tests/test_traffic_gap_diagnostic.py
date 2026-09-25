"""道路坐标中的前后车辆统计与空档区间。"""

import sys
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))

from traffic_gap_diagnostic import measure, sparse_intervals

from traffic import Road
from vehicle_state import CarState


def test_measure_counts_only_active_cars_in_road_frame():
    road = Road("endless", seed=7, shape="hills")

    def car(s, lateral=0, active=True, generation=0):
        p = road.sample_lateral(s, lateral)
        return CarState((p.x, p.y, p.z + 0.55), speed=24,
                        active=active, generation=generation)

    state = SimpleNamespace(tick=120, time=1, player=car(2000), traffic=(
        car(2100, 4.5), car(2299, -4.5), car(1600), car(3100),
        car(2010, active=False, generation=1),
    ))
    drivers = [SimpleNamespace(lane=i % 3, phase="cruise") for i in range(5)]
    sample = measure(road, state, drivers)
    assert sample["active"] == 4 and sample["retired"] == 1
    assert (sample["ahead"], sample["behind"]) == (3, 1)
    assert (sample["ahead_150"], sample["ahead_300"], sample["ahead_600"]) == (1, 2, 2)
    assert (sample["behind_150"], sample["behind_300"], sample["behind_600"]) == (0, 0, 1)
    assert abs(sample["nearest_ahead"] - 100) < 0.1
    assert abs(sample["nearest_behind"] - 400) < 0.1
    assert sample["cars"][4]["retired"] and sample["cars"][4]["generation"] == 1
    assert abs(sample["cars"][0]["relative_lateral"] - 4.5) < 0.1


def test_sparse_interval_uses_both_sides_and_retains_events():
    samples = [
        {"time": t, "player_s": 100 + t * 20, "ahead_150": front,
         "behind_150": rear}
        for t, front, rear in ((0, 2, 0), (1, 1, 0), (2, 0, 0),
                               (3, 0, 1), (4, 1, 1))
    ]
    events = [{"time": 2, "type": "recycle", "id": 3}]
    longest = sparse_intervals(samples, events, threshold=1)[0]
    assert (longest["start_time"], longest["end_time"], longest["duration_s"]) == (1, 3, 2)
    assert (longest["start_s"], longest["end_s"]) == (120, 160)
    assert longest["events"] == events
