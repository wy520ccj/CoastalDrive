"""本机原岩壁的几何、距离档和数组层不能在转换时混入代理或颠倒。"""

import io
import sys
from pathlib import Path

import numpy as np
import pytest
from panda3d.core import GeomVertexReader
from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools/environment'))

from hd2_local_rocks import SOURCE, accessor, image_bytes, load_rock, read_source, source_texture

pytestmark = pytest.mark.skipif(not SOURCE.is_file(), reason='需要用户授权只读导出的本机HD2原岩壁')


def test_visible_geometry_preserves_source_and_excludes_proxies():
    document, binary = read_source(SOURCE)
    root = load_rock()
    expected_triangles = (2304, 1152, 576, 288, 144)
    assert root.getNumChildren() == 5
    for level, triangles in enumerate(expected_triangles):
        name = 'g_rock_cliff_face_01' + ('' if level == 0 else '_LOD' + str(level))
        item, = [row for row in document['nodes'] if row['name'] == name and 'mesh' in row]
        source, = document['meshes'][item['mesh']]['primitives']
        geometry = root.getChild(level).node().getGeom(0)
        indices = accessor(document, binary, source['indices']).ravel()
        assert len(indices) == triangles * 3
        assert list(geometry.getPrimitive(0).getVertexList()) == indices.tolist()
        for column, key in (('vertex', 'POSITION'), ('normal', 'NORMAL')):
            reader = GeomVertexReader(geometry.getVertexData(), column)
            actual = np.array([tuple(reader.getData3f()) for _ in range(geometry.getVertexData().getNumRows())])
            original = accessor(document, binary, source['attributes'][key])
            expected = original[:, [0, 2, 1]] * [1, -1, 1]
            assert np.array_equal(actual, expected)


def test_albedo_array_keeps_each_source_layer_and_all_mip_pages():
    document, binary = read_source(SOURCE)
    index = document['materials'][1]['extras']['triplanar_detail_albedo']
    texture = source_texture(document, binary, index, 'independent-test', color=True)
    item = document['textures'][index]
    image = Image.open(io.BytesIO(image_bytes(document, binary, item['source']))).convert('RGBA')
    assert texture.getZSize() == 3
    pixels = np.frombuffer(texture.getRamImageAs('RGBA'), dtype=np.uint8).reshape(3, 1024, 1024, 4)
    expected = np.asarray(image).reshape(3, 1024, 1024, 4)[:, ::-1]
    assert np.array_equal(pixels, expected)
    for level in range(11):
        side = 1024 >> level
        assert len(texture.getRamMipmapImage(level)) == side * side * 3 * 4


def test_lods_have_continuous_ranges():
    root = load_rock()
    ranges = [(root.node().getIn(i), root.node().getOut(i)) for i in range(5)]
    assert ranges == [(70, 0), (150, 70), (260, 150), (420, 260), (700, 420)]


def test_packed_zero_alpha_never_erases_normal_and_ao_mips():
    document, binary = read_source(SOURCE)
    index = document['materials'][1]['extras']['base_normal_ao_dirt']
    texture = source_texture(document, binary, index, 'packed-normal-test')
    item = document['textures'][index]
    original = np.asarray(Image.open(io.BytesIO(image_bytes(document, binary, item['source']))))
    assert np.count_nonzero(original[:, :, 3] == 0) > original.shape[0] * original.shape[1] // 2
    # 原AO最暗值117；若错误地把泥土alpha当透明度预乘，远处mip会出现大量0。
    source_min = int(original[:, :, 2].min())
    assert source_min == 117
    for level in range(11):
        bgra = np.frombuffer(texture.getRamMipmapImage(level), dtype=np.uint8).reshape(-1, 4)
        assert int(bgra[:, 0].min()) >= source_min
