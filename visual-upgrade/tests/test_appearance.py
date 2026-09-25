import json

from panda3d.core import (
    AmbientLight,
    DirectionalLight,
    GeomVertexReader,
    LightAttrib,
    NodePath,
    Vec4,
)

from scene import Scene, make_mesh
from settings import AppearanceStore
from skins import MODELS, SKINS, apply_skin, traffic_models, traffic_skins
from vehicle_config import WHEEL_HUBS
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


def test_vehicle_detail_respects_existing_wheel_hubs_and_collision_outline():
    parent = NodePath("vehicle-fit")
    for definition in MODELS:
        car, wheels = load_vehicle(parent, definition.id)
        body = car.getChild(0)
        low, high = body.getTightBounds()
        assert max(abs(low.x), abs(high.x)) <= 0.95 + 0.005
        assert max(abs(low.y), abs(high.y)) <= 2.145 + 0.005
        assert len(wheels) == len(WHEEL_HUBS) == 4
        for pivot, hub in zip(wheels, WHEEL_HUBS):
            assert all(abs(actual - expected) < 1e-6 for actual, expected in zip(pivot.getPos(), hub[:2] + (-0.12,)))
        for name in ("front-grille", "headlamp", "tail-lamp", "mirror", "door-seam"):
            assert body.findAllMatches(f"**/{name}").getNumPaths() > 0
        apply_skin(body, 0)
        paint = body.find("**/paint")
        assert paint.getMaterial().getRoughness() < 0.3
        assert paint.getMaterial().getMetallic() > 0.15


def test_appearance_choices_do_not_advance_traffic_randomness(tmp_path):
    before = traffic_models(17, 18), traffic_skins(17, 18)
    store = AppearanceStore(tmp_path / "appearance.json")
    for model in MODELS:
        for skin in SKINS:
            store.save(model.id, skin.id)
    assert before == (traffic_models(17, 18), traffic_skins(17, 18))


def test_start_grid_uses_depth_priority_without_lifting_geometry():
    scene = Scene.__new__(Scene)
    scene.render = NodePath("grid-test")
    scene.add_start_grid()
    tiles = scene.render.findAllMatches("**/start-grid")
    assert tiles.getNumPaths() == 24
    for tile in tiles:
        assert tile.getDepthOffset() == 2
        data = tile.node().getGeom(0).getVertexData()
        reader = GeomVertexReader(data, "vertex")
        while not reader.isAtEnd():
            assert abs(reader.getData3f().z) < 0.05


def test_rail_receives_local_unshadowed_sun():
    scene = Scene.__new__(Scene)
    scene.render = NodePath("rail-test")
    scene.ambient_path = scene.render.attachNewNode(AmbientLight("ambient"))
    scene.sun_path = scene.render.attachNewNode(DirectionalLight("shadow-sun"))
    scene.rail_sun_path = scene.render.attachNewNode(DirectionalLight("rail-sun"))
    rail = make_mesh("rail", [(0, 0, 0), (1, 0, 0), (0, 1, 0)],
                     [(0, 1, 2)], Vec4(1, 1, 1, 1))
    scene.stabilize_rail(rail)
    lights = rail.getState().getAttrib(LightAttrib)
    assert rail.hasLightOff()
    assert lights.getNumOnLights() == 2
    assert lights.hasOnLight(scene.ambient_path)
    assert lights.hasOnLight(scene.rail_sun_path)
