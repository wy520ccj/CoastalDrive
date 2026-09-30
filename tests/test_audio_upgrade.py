"""转速跨档、负载响应、材质选择及音乐生命周期回归。"""

import hashlib
import json
import math
from dataclasses import replace

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


def test_radio_crossfade_pause_resume_and_independent_volume():
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
    assert sound.music.playing == [True, True]
    for _ in range(10):
        sound.update(frame(0), phase("driving"), None, .1)
    assert sound.music.playing == [False, True]
    sound.set_volumes(100, 0, 60)
    sound.update(frame(0), phase("driving"), None, .1)
    assert not sound.loops_playing and sound.music.playing[1]
    sound.music.select(0)
    for _ in range(10):
        sound.update(frame(0), phase("driving"), None, .1)
    assert not any(sound.music.playing)
    sound.close()
    assert all(not active for active in sound.music.playing)


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
    assert len(manifest["assets"]) == 25
    for entry in manifest["assets"]:
        assert hashlib.sha256((root / entry["path"]).read_bytes()).hexdigest() == entry["sha256"]
    assert all(entry["duration"] > 60 for entry in manifest["assets"]
               if entry["path"].startswith("music/"))
