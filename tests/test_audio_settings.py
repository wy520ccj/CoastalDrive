import json

from settings import AppearanceStore, AudioSettingsStore


def test_audio_defaults_save_reload_and_separate_appearance(tmp_path):
    path = tmp_path / "audio.json"
    store = AudioSettingsStore(path)
    assert (store.master_volume, store.effects_volume) == (100, 100)
    assert store.save(60, 30)
    restored = AudioSettingsStore(path)
    assert (restored.master_volume, restored.effects_volume) == (60, 30)
    assert path.exists() and not (tmp_path / "appearance.json").exists()
    assert AppearanceStore(tmp_path / "appearance.json").skin_id == "orange"


def test_damaged_audio_settings_fall_back_and_out_of_range_values_are_limited(tmp_path):
    path = tmp_path / "audio.json"
    path.write_text("broken json", encoding="utf-8")
    damaged = AudioSettingsStore(path)
    assert (damaged.master_volume, damaged.effects_volume) == (100, 100)
    assert damaged.notice

    path.write_text(json.dumps({"master_volume": -12, "effects_volume": 140}), encoding="utf-8")
    limited = AudioSettingsStore(path)
    assert (limited.master_volume, limited.effects_volume) == (0, 100)
    assert "限制" in limited.notice

    path.write_text(json.dumps({"master_volume": 50, "effects_volume": "loud"}), encoding="utf-8")
    invalid = AudioSettingsStore(path)
    assert (invalid.master_volume, invalid.effects_volume) == (100, 100)
    assert invalid.notice


def test_failed_save_keeps_new_runtime_values_and_reports_notice(tmp_path):
    parent = tmp_path / "blocked"
    parent.write_text("not a directory", encoding="utf-8")
    store = AudioSettingsStore(parent / "audio.json")
    assert not store.save(40, 70)
    assert (store.master_volume, store.effects_volume) == (40, 70)
    assert store.notice
