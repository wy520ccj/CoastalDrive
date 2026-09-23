import json

from panda3d.core import NodePath

from settings import AppearanceStore
from skins import MODELS, SKINS, apply_skin, traffic_models, traffic_skins
from vehicle_visual import load_vehicle


def test_appearance_round_trip_and_removed_skin(tmp_path):
    path = tmp_path / "appearance.json"
    store = AppearanceStore(path)
    assert not store.notice
    assert store.save("sedan", "blue")
    restored = AppearanceStore(path)
    assert (restored.model_id, restored.skin_id) == ("sedan", "blue")
    path.write_text(json.dumps({"model_id": "sedan", "skin_id": "deleted"}))
    fallback = AppearanceStore(path)
    assert fallback.skin_id == "orange" and fallback.notice


def test_bad_settings_and_failed_save_keep_applied_appearance(tmp_path):
    path = tmp_path / "appearance.json"
    path.write_text("broken json")
    store = AppearanceStore(path)
    assert store.notice
    assert store.save("sports", "red")
    path.with_suffix(".tmp").mkdir()
    assert not store.save("sedan", "blue")
    assert (store.model_id, store.skin_id) == ("sports", "red")
    assert AppearanceStore(path).skin_id == "red"
    assert store.notice


def test_paint_slots_change_without_touching_trim_or_adding_geometry():
    parent = NodePath("cars")
    for definition in MODELS:
        car, wheels = load_vehicle(parent, definition.id)
        body = car.getChild(0)
        slots = body.findAllMatches("**/paint")
        assert len(slots) > 0 and len(wheels) == 4
        trim = [(part, part.getState()) for part in body.findAllMatches("**/+GeomNode") if part.getName() != "paint"]
        count = parent.findAllMatches("**").getNumPaths()
        for index, skin in enumerate(SKINS):
            apply_skin(body, index)
            assert parent.findAllMatches("**").getNumPaths() == count
            assert all(part.getState() == state for part, state in trim)
            assert all(abs(slot.getMaterial().getBaseColor()[0] - skin.color[0]) < 1e-6 for slot in slots)
        # Two copies must retain their wheels and independent paint state.
        duplicate, _ = load_vehicle(parent, definition.id)
        apply_skin(duplicate.getChild(0), 1)
        assert abs(slots[0].getMaterial().getBaseColor()[0] - SKINS[-1].color[0]) < 1e-6


def test_appearance_choices_do_not_advance_traffic_randomness(tmp_path):
    before = traffic_models(17, 18), traffic_skins(17, 18)
    store = AppearanceStore(tmp_path / "appearance.json")
    for model in MODELS:
        for skin in SKINS:
            store.save(model.id, skin.id)
    assert before == (traffic_models(17, 18), traffic_skins(17, 18))
