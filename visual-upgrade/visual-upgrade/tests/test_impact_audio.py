"""用真实事件合同检查重触发、分层和声音预算。"""

import json
from io import StringIO
from itertools import pairwise

from test_soundscape import FakeBase, contact, event

from impact_audio import ImpactAudio, severity_for
from paths import resource_root


def mixer():
    base = FakeBase()
    audio_dir = resource_root() / "assets" / "game" / "audio"
    sound = ImpactAudio(base, audio_dir)
    log = StringIO()
    sound.set_diagnostic(log)
    return sound, log


def decisions(log):
    return [json.loads(line) for line in log.getvalue().splitlines()
            if json.loads(line)["type"] == "decision"]


def test_severity_curve_is_monotone_and_not_linear_volume():
    curve = [[0, 0], [.6, .13], [2, .36], [5, .65], [10, .9], [20, 1]]
    values = [severity_for(q * 1200, curve) for q in (0, .2, .6, 2, 5, 10, 20)]
    assert values == sorted(values)
    assert values[0] == 0 and values[-1] == 1
    assert values[2] - values[1] != values[5] - values[4]


def test_same_source_cluster_upgrades_and_second_hit_plays():
    sound, log = mixer()
    for tick, impulse in ((1, 1700), (5, 1800), (6, 9000), (42, 2100)):
        sound.update((event(tick, impulse),), (), .016, 1, epoch=1)
    outcomes = decisions(log)
    assert len(outcomes) == 4
    assert outcomes[0]["layers"]
    assert outcomes[1]["suppressed"] == "same-source-cluster"
    assert outcomes[2]["layers"]
    assert outcomes[3]["layers"]


def test_multiple_contact_points_are_one_event_but_distinct_sources_play():
    sound, log = mixer()
    sound.update((event(source=1), event(source=2)), (), .016, 1, epoch=1)
    assert len(decisions(log)) == 2
    assert len(sound.voices) <= 10


def test_major_collision_rejects_weak_tail_but_allows_later_second_hit():
    sound, log = mixer()
    for tick, impulse, source in ((1, 13000, 1), (14, 240, 2), (45, 11000, 2)):
        sound.update((event(tick, impulse, source=source),), (), .016, 1, epoch=1)
    outcomes = decisions(log)
    assert outcomes[0]["layers"]
    assert outcomes[1]["suppressed"] == "major-impact-tail"
    assert outcomes[2]["layers"]


def test_tiny_solver_pulse_does_not_sound_like_another_impact():
    sound, log = mixer()
    sound.update((event(1, 25),), (), .016, 1, epoch=1)
    assert decisions(log)[0]["suppressed"] == "below-audible-floor"
    assert sound.voices == []


def test_variant_bag_never_repeats_consecutively():
    sound, log = mixer()
    for index in range(12):
        sound.update((event(1 + index * 30, source=index + 1),), (), .15, 1, epoch=1)
    transients = [next(variant for layer, variant in row["layers"] if layer == "transient")
                  for row in decisions(log)]
    assert len(transients) == 12
    assert all(left != right for left, right in pairwise(transients))


def test_complex_accident_has_fixed_voice_budget_and_one_scrape():
    sound, _ = mixer()
    sound.update(tuple(event(1, source=index + 1) for index in range(16)),
                 (contact(),), .016, 1, epoch=1)
    sound.update((), (contact(2),), .016, 1, epoch=1)
    for layer, maximum in (("transient", 3), ("body", 3), ("crunch", 2), ("debris", 2)):
        assert sum(voice.layer == layer for voice in sound.voices) <= maximum
    assert len(sound.voices) <= 10
    assert sound.scrape_sound is not None


def test_mute_and_epoch_change_do_not_queue_old_hit():
    sound, log = mixer()
    sound.update((event(),), (), .016, 0, epoch=1)
    sound.update((event(),), (), .016, 1, epoch=1)
    assert decisions(log) == []
    sound.update((event(1, epoch=2),), (), .016, 1, epoch=2)
    assert len(decisions(log)) == 1
    assert all(voice.event_id.startswith("2:") for voice in sound.voices)
