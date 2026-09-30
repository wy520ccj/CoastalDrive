"""转速跨档、负载响应、材质选择及音乐生命周期回归。"""

import hashlib
import json
import math
from dataclasses import replace
from itertools import pairwise

from panda3d.core import AudioManager
from test_soundscape import event, frame, make_soundscape, phase

from audio.engine import RPM_BANDS, band_mix
from paths import resource_root
from settings import AudioSettingsStore
from simulation import Simulation


def test_rpm_band_boundaries_keep_equal_power_and_matching_firing_rate():
    for rpm in range(900, 7601, 17):
        lower, upper, left, right = band_mix(rpm)
        assert upper - lower == 1
        assert abs(left * left + right * right - 1) < 1e-12
        assert 0 <= left <= 1 and 0 <= right <= 1
    sound, _ = make_soundscape()
    sound.update(frame(0, rpm=3900), phase("driving"), None, .1)
    for i, pair in enumerate(sound.engine_audio.layers):
        assert abs(pair[0].rate * RPM_BANDS[i] - sound.engine_audio.rpm) < 1e-8


def test_load_changes_timbre_and_shift_releases_after_short_cut():
    sound, _ = make_soundscape()
    steady = frame(0, rpm=3200)
    steady.player = replace(steady.player, throttle=1)
    for _ in range(10):
        sound.update(steady, phase("driving"), None, .1)
    coast, loaded = sound.engine_audio.layers[2]
    assert loaded.volumes[-1] > coast.volumes[-1] * 10
    level = sound.engine_audio.level
    steady.player = replace(steady.player, gear=2)
    sound.update(steady, phase("driving"), None, .03)
    assert sound.engine_audio.level < level
    for _ in range(10):
        sound.update(steady, phase("driving"), None, .1)
    assert math.isclose(sound.engine_audio.level, level, abs_tol=.002)
    steady.player = replace(steady.player, throttle=0)
    for _ in range(10):
        sound.update(steady, phase("driving"), None, .1)
    assert coast.volumes[-1] > loaded.volumes[-1] * 10


def test_default_engine_leaves_headroom_for_collision_and_radio():
    sound, _ = make_soundscape()
    state = frame(0, rpm=6500)
    state.player = replace(state.player, throttle=1)
    for _ in range(20):
        sound.update(state, phase("driving"), None, .1)
    assert sound.engine_audio.level <= .191
    sound.update(frame(0, (event(1, 12000),)), phase("driving"), None, .016)
    attack = next(voice for voice in sound.impact_audio.voices if voice.layer == "transient")
    body = next(voice for voice in sound.impact_audio.voices if voice.layer == "body")
    assert body.gain > .90
    assert body.gain > attack.gain * 1.3


def test_music_format_headroom_and_distinct_licensed_sources():
    import wave
    from array import array

    root = resource_root() / "assets/game/audio"
    credits = json.loads((root / "music-sources.json").read_text(encoding="utf-8"))
    tracks = credits["tracks"]
    assert {t["isrc"] for t in tracks} == {"USUAN1700069", "USUAN1200051"}
    assert len({t["source_sha256"] for t in tracks}) == 2
    assert all(t["author"] == "Kevin MacLeod" and t["license"] == "CC BY 4.0" for t in tracks)
    for path in (root / "music").glob("*.wav"):
        with wave.open(str(path), "rb") as clip:
            assert (clip.getframerate(), clip.getnchannels(), clip.getsampwidth()) == (44100, 2, 2)
            pcm = array("h", clip.readframes(clip.getnframes()))
        assert 0 < max(abs(x) for x in pcm) / 32768 < .7
    # 首页完整保留已交付的原海岸曲，而不是重新生成一首近似曲。
    assert hashlib.sha256((root / "music/home-coast.wav").read_bytes()).hexdigest() == (
        "c0a3a3cf5a528286bad98fea1104d5a68279e0f2c14e0db765d54703e44fbf0f")


def test_surface_and_braking_are_speed_gated():
    sound, _ = make_soundscape()
    state = frame(0, speed=0)
    state.player = replace(state.player, brake=1, lateral_acceleration=15)
    sound.update(state, phase("driving"), None, .1)
    assert sound.driving_audio.levels["tire"] == 0
    state.player = replace(state.player, speed=28)
    for _ in range(10):
        sound.update(state, phase("driving"), None, .1)
    assert sound.driving_audio.levels["tire"] > .08
    state.player = replace(state.player, surface="grass")
    for _ in range(10):
        sound.update(state, phase("driving"), None, .1)
    assert sound.driving_audio.levels["gravel"] > .10
    assert sound.driving_audio.levels["tire"] < .001


def test_radio_switch_pause_resume_and_independent_volume():
    sound, _ = make_soundscape()
    for _ in range(12):
        sound.update(frame(0), phase("driving"), None, .1)
    track = sound.music.tracks[0]
    track.time = 17.5
    sound.update(frame(0), phase("paused"), None, .1)
    assert not any(sound.music.playing)
    sound.update(frame(0), phase("driving"), None, .1)
    assert track.time == 17.5
    for _ in range(10):
        sound.update(frame(0), phase("driving"), None, .1)
    sound.music.select(2)
    sound.update(frame(0), phase("driving"), None, .1)
    assert sound.music.playing == [False, True, False]
    for _ in range(10):
        sound.update(frame(0), phase("driving"), None, .1)
    assert sound.music.playing == [False, True, False]
    sound.set_volumes(100, 0, 60)
    sound.update(frame(0), phase("driving"), None, .1)
    assert not sound.loops_playing and sound.music.playing[1]
    sound.music.select(0)
    for _ in range(10):
        sound.update(frame(0), phase("driving"), None, .1)
    assert not any(sound.music.playing)
    sound.close()
    assert all(not active for active in sound.music.playing)


def test_home_bgm_radio_preview_pause_and_driving_use_separate_tracks():
    sound, _ = make_soundscape()
    sound.music.select(2)
    for _ in range(10):
        sound.update(frame(0), phase("menu"), None, .1)
    assert sound.music.playing == [False, False, True]
    assert sound.music.tracks[2].path.endswith("home-coast.wav")
    sound.update(frame(0), phase("paused"), None, .1)
    assert sound.music.playing == [False, False, False]
    sound.music.select(1)
    for _ in range(10):
        sound.update(frame(0), phase("paused"), None, .1, music_preview=True)
    assert sound.music.playing == [True, False, False]
    assert not sound.loops_playing
    sound.music.select(0)
    for _ in range(10):
        sound.update(frame(0), phase("menu"), None, .1, music_preview=True)
    assert sound.music.playing == [False, False, False]
    for _ in range(10):
        sound.update(frame(0), phase("menu"), None, .1)
    assert sound.music.playing == [False, False, True]
    sound.music.select(2)
    for _ in range(10):
        sound.update(frame(0), phase("driving"), None, .1)
        assert sum(sound.music.playing) <= 1
    assert sound.music.playing == [False, True, False]
    sound.close()


def test_collision_materials_choose_different_weight_and_attack_layers():
    selections = []
    for material in ("vehicle", "metal_barrier", "hard_solid"):
        sound, _ = make_soundscape()
        sound.update(frame(0, (event(1, 12000, material=material),)), phase("driving"), None)
        selections.append({v.layer: v.variant.rsplit("_", 1)[0]
                           for v in sound.impact_audio.voices})
        sound.close()
    assert len({s["body"] for s in selections}) == 3
    assert len({s["transient"] for s in selections}) == 3
    assert all("crunch" in s and "debris" in s for s in selections)


def test_standalone_collision_finishes_without_baked_in_sliding_tail():
    for material in ("vehicle", "metal_barrier", "hard_solid"):
        sound, _ = make_soundscape()
        sound.update(frame(0, (event(1, 22000, material=material),)), phase("driving"), None)
        assert sound.impact_audio.voices
        for tick in range(1, 34):
            sound.update(frame(tick/60), phase("driving"), None, 1/60)
        assert sound.impact_audio.voices == []
        assert sound.impact_audio.scrape_sound is None


def test_wider_current_chassis_corner_keeps_head_on_contact_zone():
    assert Simulation._contact_zone((-1.05, 2.15, .42), (0, -1, 0)) == "front"
    assert Simulation._contact_zone((1.05, 2.15, .42), (-1, 0, 0)) == "right"


def test_audio_settings_migrate_old_file_and_save_radio(tmp_path):
    path = tmp_path / "audio.json"
    path.write_text('{"master_volume": 70, "effects_volume": 80}')
    store = AudioSettingsStore(path)
    assert (store.master_volume, store.effects_volume, store.music_volume) == (70, 80, 55)
    assert store.save(70, 80, 45, 2)
    restored = AudioSettingsStore(path)
    assert (restored.music_volume, restored.radio_station) == (45, 2)


def test_upgrade_manifest_matches_actual_assets():
    root = resource_root() / "assets/game/audio"
    manifest = json.loads((root / "upgrade-manifest.json").read_text())
    assert len(manifest["assets"]) == 26
    for entry in manifest["assets"]:
        assert hashlib.sha256((root / entry["path"]).read_bytes()).hexdigest() == entry["sha256"]
    assert all(entry["duration"] > 60 for entry in manifest["assets"]
               if entry["path"].startswith("music/"))


def test_radio_preloads_samples_and_never_overlaps_during_rapid_switches():
    sound, _ = make_soundscape()
    assert all(track.mode == AudioManager.SM_sample for track in sound.music.tracks)
    for tick in range(300):
        if tick % 7 == 0:
            sound.music.select((tick // 7) % 3)
        state = phase("paused" if tick % 31 == 0 else "driving")
        sound.update(frame(tick/120), state, None, 1/120)
        assert sum(sound.music.playing) <= 1
    sound.music.select(2)
    for _ in range(24):
        sound.update(frame(0), phase("driving"), None, 1/120)
    assert sound.music.playing == [False, True, False]
    sound.close()


def test_recorded_engine_loops_have_signal_and_no_seam_spike():
    import wave
    from array import array

    root = resource_root() / "assets/game/audio"
    for path in (root / "engine").glob("*.wav"):
        with wave.open(str(path), "rb") as clip:
            samples = array("h", clip.readframes(clip.getnframes()))
        assert len(samples) >= .3 * 44100
        # 环缝跳变须落在实录正常相邻采样差值内，避免每圈固定出现一次爆音。
        derivative_rms = math.sqrt(sum((b-a)**2 for a, b in pairwise(samples))
                                   / (len(samples)-1))
        assert derivative_rms > 1
        assert abs(samples[0]-samples[-1]) < derivative_rms * 4
