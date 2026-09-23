"""驾驶循环音量与真实碰撞事件的集成检查。"""

import json
import wave
from io import StringIO
from types import SimpleNamespace

from impact_events import ContactState, ImpactEvent
from paths import resource_root
from soundscape import Soundscape


class FakeSound:
    def __init__(self):
        self.volumes = []
        self.play_count = 0
        self.stop_count = 0
        self.rate = 1.0
        self.position = None

    def setLoop(self, value):
        self.loop = value

    def setVolume(self, value):
        self.volumes.append(value)

    def setPlayRate(self, value):
        self.rate = value

    def set3dAttributes(self, *values):
        self.position = values

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


def event(tick=1, impulse=6000, *, epoch=1, source=1, material="metal_barrier", zone="front"):
    return ImpactEvent(epoch, tick, source - 1, (source,), material, impulse, impulse,
                       8.0, 0.3, (0, 2, 0.4), (0, -1, 0), zone, 1)


def contact(tick=1, *, tangent=8.0, impulse=150, source=1):
    return ContactState((source,), "metal_barrier", tick, impulse, 0.0, tangent,
                        (0.8, 0, 0.4), (-1, 0, 0), "right", tick)


def frame(time, impacts=(), contacts=(), *, epoch=1, rpm=3500, speed=18):
    player = SimpleNamespace(throttle=0.5, speed=speed, rpm=rpm, surface="asphalt")
    return SimpleNamespace(time=time, impacts=impacts, contacts=contacts,
                           contact_epoch=epoch, player=player, collisions=0)


def phase(value):
    return SimpleNamespace(value=value)


def make_soundscape(master=100, effects=100):
    base = FakeBase()
    soundscape = Soundscape(base, master, effects)
    return soundscape, base.sounds


def impact_plays(sounds):
    return sum(sound.play_count for sound in sounds[3:])


def test_volume_levels_multiply_loops_and_all_impact_layers():
    full, a = make_soundscape()
    reduced, b = make_soundscape(50, 20)
    for soundscape in (full, reduced):
        soundscape.update(frame(0), phase("driving"), None)
        soundscape.update(frame(.1, (event(),)), phase("driving"), None)
    for i in range(3):
        assert abs(b[i].volumes[-1] - a[i].volumes[-1] * .1) < 1e-9
    assert len(full.impact_audio.voices) >= 2
    assert len(reduced.impact_audio.voices) == len(full.impact_audio.voices)
    for left, right in zip(full.impact_audio.voices, reduced.impact_audio.voices):
        assert abs(right.sound.volumes[-1] - left.sound.volumes[-1] * .1) < 1e-9


def test_idle_and_revs_preserve_existing_mix():
    soundscape, sounds = make_soundscape()
    soundscape.update(frame(0, rpm=900), phase("driving"), None)
    assert sounds[1].volumes[-1] > 0 and sounds[0].volumes[-1] == 0
    soundscape.update(frame(.1, rpm=8000, speed=36), phase("driving"), None)
    assert sounds[0].volumes[-1] > 0 and sounds[1].volumes[-1] == 0
    assert sounds[2].volumes[-1] < sounds[0].volumes[-1]


def test_mute_consumes_impact_without_replay():
    soundscape, sounds = make_soundscape(0, 100)
    soundscape.update(frame(0, (event(),)), phase("driving"), None)
    assert impact_plays(sounds) == 0
    soundscape.set_volumes(100, 100)
    soundscape.update(frame(.1, (event(),)), phase("driving"), None)
    assert impact_plays(sounds) == 0
    soundscape.update(frame(.2, (event(25),)), phase("driving"), None)
    assert impact_plays(sounds) >= 2
    soundscape.set_volumes(100, 0)
    assert soundscape.impact_audio.voices == []
    assert all(sound.volumes[-1] == 0 for sound in sounds[:3])


def test_pause_resume_reset_and_close_stop_all_voices():
    soundscape, sounds = make_soundscape()
    soundscape.update(frame(0, (event(),)), phase("driving"), None)
    assert soundscape.impact_audio.voices
    soundscape.update(frame(.1), phase("paused"), None)
    assert soundscape.impact_audio.voices == []
    assert not soundscape.loops_playing
    soundscape.update(frame(.2), phase("driving"), None)
    assert [s.play_count for s in sounds[:3]] == [2, 2, 2]
    soundscape.update(frame(.3, (event(1, epoch=2),), epoch=2), phase("driving"), None)
    assert all(v.event_id.startswith("2:") for v in soundscape.impact_audio.voices)
    soundscape.close()
    soundscape.close()
    assert soundscape.impact_audio.voices == []
    assert not soundscape.loops_playing


def test_only_physical_event_triggers_sound_and_scrape_is_loop():
    soundscape, sounds = make_soundscape()
    soundscape.update(frame(0), phase("driving"), None)
    for tick in range(1, 15):
        soundscape.update(frame(tick / 120, contacts=(contact(tick),)),
                          phase("driving"), None, 1 / 120)
    assert impact_plays(sounds) == 1
    assert soundscape.impact_audio.scrape_sound is not None
    scrape_sound = soundscape.impact_audio.scrape_sound
    assert scrape_sound.play_count == 1 and scrape_sound.loop
    assert soundscape.impact_audio.scrape_state == "sustain"
    for tick in range(15, 34):
        soundscape.update(frame(tick / 120), phase("driving"), None, 1 / 120)
    assert scrape_sound.stop_count == 1
    assert soundscape.impact_audio.scrape_state == "off"


def test_audio_log_reports_severity_layers_and_scrape():
    soundscape, _ = make_soundscape()
    log = StringIO()
    soundscape.set_impact_diagnostic(log)
    soundscape.update(frame(0, (event(zone="left"),)), phase("driving"), None)
    decisions = [json.loads(line) for line in log.getvalue().splitlines()
                 if json.loads(line)["type"] == "decision"]
    assert decisions[0]["material"] == "metal_barrier"
    assert decisions[0]["zone"] == "left"
    assert decisions[0]["raw_impulse"] == 6000
    assert 0 < decisions[0]["severity"] < 1
    assert {name for name, _ in decisions[0]["layers"]} >= {"transient", "body"}
    assert all(v.sound.position[0] == -0.16 for v in soundscape.impact_audio.voices)


def test_new_impact_clips_are_playable_mono_pcm():
    audio_dir = resource_root() / "assets" / "game" / "audio"
    bank = json.loads((audio_dir / "impact-bank.json").read_text(encoding="utf-8"))
    assert sum(map(len, bank["pools"].values())) == 22
    for pool in bank["pools"].values():
        for entry in pool:
            with wave.open(str(audio_dir / entry["path"]), "rb") as clip:
                assert clip.getnchannels() == 1
                assert clip.getsampwidth() == 2
                assert clip.getframerate() == 44100
                assert clip.getnframes() > 8000
