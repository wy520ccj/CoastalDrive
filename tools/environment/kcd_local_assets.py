"""只读本机KCD2标准资源包，供用户指定的本地视觉试验使用。"""

import hashlib
import io
import json
import struct
from pathlib import Path
from zipfile import ZipFile

from panda3d.core import AlphaTestAttrib, Filename, Material, Texture, TextureStage, Vec3
from PIL import Image

from environment.surface_mesh import surface_mesh

INSTALL = Path('D:/SteamLibrary/steamapps/common/KingdomComeDeliverance2/Data')
GRASS = 'Objects/natural/vegetation/grass/grass_groups/'
TREE = 'Objects/natural/vegetation/trees/normal_trees/quercus_robur/'


def read_mesh(raw):
    signature, version, count, table = struct.unpack_from('<4sIII', raw)
    if signature != b'CrCh' or version != 0x746:
        raise ValueError('仅支持本次确认的CrCh 0x746格式')
    chunks = {}
    for i in range(count):
        kind, revision, key, size, offset = struct.unpack_from('<HHIII', raw, table + i * 16)
        chunks[key] = (kind, revision, raw[offset:offset + size])
    meshes = [body for kind, revision, body in chunks.values() if kind == 0x1000 and revision == 0x801]
    if len(meshes) != 1:
        raise ValueError('样板要求单一可见网格')
    mesh = meshes[0]
    streams = struct.unpack_from('<16i', mesh, 28)
    vertices = chunks[streams[15]][2]
    indices = chunks[streams[5]][2]
    tangents = chunks[streams[6]][2]
    assert struct.unpack_from('<3I', vertices, 4)[::2] == (15, 16)
    points, normals, uv = [], [], []
    for i in range(struct.unpack_from('<I', vertices, 8)[0]):
        x, y, z, _, _r, _g, _b, _a, u, v = struct.unpack_from('<4e4B2e', vertices, 24 + i * 16)
        t = struct.unpack_from('<8h', tangents, 24 + i * 16)
        normal = Vec3(*t[4:7]).cross(Vec3(*t[:3]))
        if t[3] > 0:
            normal = -normal
        normal.normalize()
        points.append((x, y, z))
        normals.append(tuple(normal))
        uv.append((u, 1 - v))
    total = struct.unpack_from('<I', indices, 8)[0]
    values = struct.unpack_from('<' + str(total) + 'H', indices, 24)
    subset = chunks[struct.unpack_from('<i', mesh, 20)[0]][2]
    material_ids, faces = [], []
    for n in range(struct.unpack_from('<I', subset, 4)[0]):
        first, length, _start_vertex, _vertices, material = struct.unpack_from('<5i', subset, 16 + n * 36)
        material_ids.append(material)
        # 材质2是原引擎的阴影代理，不应作为可见枝叶绘制。
        if material == 2:
            continue
        selected = values[first:first + length]
        faces.extend(zip(selected[::3], selected[1::3], selected[2::3], strict=True))
    return {'points': points, 'normals': normals, 'uv': uv, 'faces': faces,
            'material_ids': material_ids, 'sha256': hashlib.sha256(raw).hexdigest()}


def decode_texture(package, name, suffix, size, output):
    header = bytearray(package.read(name)[:148])
    payload = package.read(name + suffix)
    struct.pack_into('<II', header, 12, size[1], size[0])
    struct.pack_into('<I', header, 28, 1)
    # BC3 sRGB与BC3线性共享压缩位布局；Pillow解码后由Panda恢复sRGB语义。
    compression = struct.unpack_from('<I', header, 128)[0]
    struct.pack_into('<I', header, 128, {78: 77, 72: 71}[compression])
    decoded = Image.open(io.BytesIO(header + payload)).convert('RGBA')
    decoded.save(output)
    texture = Texture(output.stem)
    if not texture.read(Filename.fromOsSpecific(str(output))):
        raise OSError(output)
    texture.setFormat(Texture.FSrgbAlpha)
    texture.setMinfilter(Texture.FTLinearMipmapLinear)
    texture.setAnisotropicDegree(8)
    return texture


def model(name, mesh, texture, shader):
    node = surface_mesh(name, mesh['points'], mesh['faces'], mesh['normals'],
                        [(1, 1, 1, 1)] * len(mesh['points']), mesh['uv'])
    stage = TextureStage('Base Color')
    node.setTexture(stage, texture)
    material = Material(name)
    material.setBaseColor((1, 1, 1, 1))
    material.setRoughness(.9)
    material.setMetallic(0)
    node.setMaterial(material)
    node.setTwoSided(True)
    node.setAttrib(AlphaTestAttrib.make(AlphaTestAttrib.MGreaterEqual, .25))
    node.setShader(shader, 2)
    node.setShaderInput('foliage_alpha_cutoff', .25)
    return node


def load_local(output, shader):
    output.mkdir(parents=True, exist_ok=True)
    trees, grasses, record = [], [], []
    with ZipFile(INSTALL / 'IPL_Objects-part5.pak') as package:
        texture = decode_texture(package, TREE + 'quercus_atlas_diff.dds', '.5', (2048, 1024), output / 'oak.png')
        for letter in 'abc':
            name = TREE + 'quercus_' + letter + '.cgfm'
            mesh = read_mesh(package.read(name))
            if not set(mesh['material_ids']) <= {1, 2, 3, 6, 10, 12}:
                raise ValueError((name, mesh['material_ids']))
            trees.append(model('kcd-oak-' + letter, mesh, texture, shader))
            record.append({'source': name, 'triangles': len(mesh['faces']), 'sha256': mesh['sha256']})
    with ZipFile(INSTALL / 'IPL_Objects-part4.pak') as package:
        texture = decode_texture(package, GRASS + 'plants_grass_merged_diff.dds', '.6', (2048, 2048), output / 'grass.png')
        for letter in 'abc':
            name = GRASS + 'grass_green_' + letter + '.cgfm'
            mesh = read_mesh(package.read(name))
            grasses.append((mesh, texture))
            record.append({'source': name, 'triangles': len(mesh['faces']), 'sha256': mesh['sha256']})
    (output / 'local-source.json').write_text(json.dumps({
        'scope': '用户指定的本机KCD2资源试验；原件只读；衍生资源仅存ignored logs，不作为可分发资产',
        'installation': str(INSTALL), 'meshes': record,
    }, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    with ZipFile(INSTALL / 'IPL_Textures-part1.pak') as package:
        ground = decode_texture(package, 'Textures/terrain/grass/grass_pasture_a_2x2_diff.dds',
                                '.5', (1024, 1024), output / 'pasture.png')
    return trees, grasses, ground
