from types import SimpleNamespace

from minimap import MinimapRenderer
from traffic import Road


def snapshot(x, y, heading=0):
    return SimpleNamespace(player=SimpleNamespace(position=(x, y, 0.42), heading=heading))


def test_coastal_minimap_is_round_and_uses_track_texture():
    road = Road("coastal")
    renderer = MinimapRenderer(192)
    texture = renderer.update(snapshot(95, 8, 90), "coastal", road)
    pixels = bytes(texture.getRamImageAs("RGBA"))
    assert texture.getXSize() == texture.getYSize() == 192
    assert len(pixels) == 192 * 192 * 4
    assert pixels[3] == 0
    middle = ((96 * 192 + 96) * 4) + 3
    assert pixels[middle] == 255


def test_endless_minimap_uses_local_road_after_coordinate_rebase():
    road = Road("endless", seed=17)
    renderer = MinimapRenderer(256)
    renderer.update(snapshot(0, 2010), "endless", road, 0)
    before = bytes(renderer.texture.getRamImageAs("RGBA"))
    road.origin_y = 2000
    renderer.update(snapshot(0, 10), "endless", road, 2000)
    after = bytes(renderer.texture.getRamImageAs("RGBA"))
    assert before == after
