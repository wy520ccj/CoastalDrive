import wave
from types import SimpleNamespace

from paths import resource_root
from soundscape import Soundscape, collision_sound_kind


class FakeSound:
    def __init__(self):
        self.volumes = []
        self.play_count = 0
        self.stop_count = 0

    def setLoop(self, value):
        self.loop = value

    def setVolume(self, value):
        self.volumes.append(value)

    def setPlayRate(self, value):
        self.rate = value

    def play(self):
        self.play_count += 1

    def stop(self):
        self.stop_count += 1


class FakeBase:
    def __init__(self):
        self.sounds = []
        self.loader = SimpleNamespace(loadSfx=self.load_sound)

    def load_sound(self, _path):
        sound = FakeSound()
        self.sounds.append(sound)
        return sound


def frame(
    time,
    collisions=0,
    *,
    throttle=0.5,
    speed=18,
    rpm=3500,
    surface="asphalt",
    velocity=None,
    heading=0,
):
    if velocity is None:
        velocity = (0.0, speed, 0.0)
    player = SimpleNamespace(
        throttle=throttle,
        speed=speed,
        rpm=rpm,
        surface=surface,
        velocity=velocity,
        heading=heading,
    )
    return SimpleNamespace(time=time, collisions=collisions, player=player)


def phase(value):
    return SimpleNamespace(value=value)


def make_soundscape(master=100, effects=100):
    base = FakeBase()
    soundscape = Soundscape(base, master, effects)
    return soundscape, base.sounds


def test_both_volume_levels_multiply_engine_road_and_collision_audio():
    full, full_sounds = make_soundscape()
    reduced, reduced_sounds = make_soundscape(50, 20)
    for soundscape in (full, reduced):
        soundscape.update(frame(0, 0), phase("driving"), None)
        soundscape.update(frame(0.1, 1), phase("driving"), None)
    for index in range(3):
        assert abs(reduced_sounds[index].volumes[-1] - full_sounds[index].volumes[-1] * 0.1) < 1e-9
    assert full_sounds[3].play_count == reduced_sounds[3].play_count == 1
    assert abs(reduced_sounds[3].volumes[-1] - full_sounds[3].volumes[-1] * 0.1) < 1e-9


def test_real_idle_and_revs_mix_by_rpm_with_subtle_road_level():
    soundscape, sounds = make_soundscape()
    soundscape.update(frame(0, rpm=900), phase("driving"), None)
    assert sounds[1].volumes[-1] > 0 and sounds[0].volumes[-1] == 0
    soundscape.update(frame(0.1, rpm=8000, speed=36), phase("driving"), None)
    assert sounds[0].volumes[-1] > 0 and sounds[1].volumes[-1] == 0
    assert sounds[2].volumes[-1] < sounds[0].volumes[-1]


def test_mute_consumes_collisions_and_does_not_replay_them_after_unmute():
    soundscape, sounds = make_soundscape(0, 100)
    soundscape.update(frame(0, 0), phase("driving"), None)
    soundscape.update(frame(0.1, 1), phase("driving"), None)
    assert not soundscape.loops_playing
    assert all(sound.play_count == 0 for sound in sounds)
    soundscape.set_volumes(100, 100)
    soundscape.update(frame(0.2, 1), phase("driving"), None)
    assert sum(sound.play_count for sound in sounds[3:]) == 0
    soundscape.update(frame(0.3, 2), phase("driving"), None)
    assert sum(sound.play_count for sound in sounds[3:]) == 1
    soundscape.set_volumes(100, 0)
    soundscape.update(frame(0.4, 3), phase("driving"), None)
    assert all(sound.volumes[-1] == 0 for sound in sounds[:3])
    assert sounds[3].play_count == 1


def test_recorded_crash_has_time_to_ring_out_between_collisions():
    soundscape, sounds = make_soundscape()
    soundscape.update(frame(0, 0), phase("driving"), None)
    soundscape.update(frame(0.1, 1), phase("driving"), None)
    soundscape.update(frame(0.4, 2), phase("driving"), None)
    assert sum(sound.play_count for sound in sounds[3:]) == 1
    soundscape.update(frame(0.9, 3), phase("driving"), None)
    assert sum(sound.play_count for sound in sounds[3:]) == 2


def test_collision_sound_selection_covers_light_side_scrape_and_heavy_impacts():
    assert collision_sound_kind((0, 18, 0), (0, 17.5, 0), 0, 18) == "light"
    assert collision_sound_kind((4, 18, 0), (1, 18, 0), 0, 18) == "side"
    assert collision_sound_kind((5.2, 18, 0), (4.0, 18, 0), 0, 18) == "scrape"
    assert collision_sound_kind((0, 22, 0), (0, 18, 0), 0, 18) == "heavy"


def test_collision_classes_play_different_recordings():
    cases = (
        ("light", (0, 18, 0), (0, 17.5, 0), 18),
        ("side", (4, 18, 0), (1, 18, 0), 18),
        ("scrape", (5.2, 18, 0), (4.0, 18, 0), 18),
        ("heavy", (0, 22, 0), (0, 18, 0), 18),
    )
    for kind, previous, current, speed in cases:
        soundscape, sounds = make_soundscape()
        soundscape.previous_velocity = previous
        soundscape.update(frame(1, 1, velocity=current, speed=speed), phase("driving"), None)
        expected = 3 + ("light", "side", "scrape", "heavy").index(kind)
        assert sounds[expected].play_count == 1
        assert sum(sound.play_count for sound in sounds[3:]) == 1
        for sound in sounds[3:]:
            if sound is not sounds[expected]:
                assert sound.play_count == 0


def test_pause_resume_reuses_one_loop_instance_and_close_stops_every_sound():
    soundscape, sounds = make_soundscape()
    soundscape.update(frame(0, 0), phase("driving"), None)
    soundscape.update(frame(0.1, 0), phase("driving"), None)
    assert [sound.play_count for sound in sounds[:3]] == [1, 1, 1]
    assert sum(sound.play_count for sound in sounds[3:]) == 0

    soundscape.update(frame(0.2, 0), phase("paused"), None)
    assert not soundscape.loops_playing
    assert all(sound.stop_count == 1 for sound in sounds[:3])
    soundscape.update(frame(0.3, 0), phase("driving"), None)
    assert [sound.play_count for sound in sounds[:3]] == [2, 2, 2]
    assert sum(sound.play_count for sound in sounds[3:]) == 0

    soundscape.close()
    soundscape.close()
    assert not soundscape.loops_playing
    assert [sound.stop_count for sound in sounds] == [2, 2, 2, 1, 1, 1, 1]


def test_menu_results_and_countdown_loop_lifecycle():
    soundscape, sounds = make_soundscape()
    soundscape.update(frame(0, 0), phase("menu"), None)
    soundscape.update(frame(0.1, 0), phase("countdown"), None)
    soundscape.update(frame(0.2, 0), phase("results"), None)
    soundscape.update(frame(0.3, 0), phase("driving"), None)
    assert [sound.play_count for sound in sounds[:3]] == [2, 2, 2]
    assert sum(sound.play_count for sound in sounds[3:]) == 0
    assert all(sound.stop_count == 1 for sound in sounds[:3])


def test_recorded_clips_have_runtime_pcm_format():
    audio_dir = resource_root() / "assets" / "game" / "audio"
    for name in (
        "engine.wav",
        "engine_idle.wav",
        "road.wav",
        "impact_light.wav",
        "impact_side.wav",
        "impact_scrape.wav",
        "impact_heavy.wav",
    ):
        with wave.open(str(audio_dir / name), "rb") as clip:
            assert clip.getnchannels() == 1
            assert clip.getsampwidth() == 2
            assert clip.getframerate() == 44100
            assert clip.getnframes() > 8000
