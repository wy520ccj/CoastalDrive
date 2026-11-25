"""只读本机KCD2标准资源包，供用户指定的本地视觉试验使用。"""

import hashlib
import io
import json
import os
import struct
import xml.etree.ElementTree as ET
from pathlib import Path
from zipfile import ZipFile

import numpy as np
from panda3d.core import (
    AlphaTestAttrib,
    FadeLODNode,
    Filename,
    LODNode,
    Material,
    NodePath,
    PTAUchar,
    Texture,
    TextureStage,
    Vec3,
)
from PIL import Image

from environment.surface_mesh import surface_mesh

INSTALL = Path('D:/SteamLibrary/steamapps/common/KingdomComeDeliverance2/Data')
GRASS = 'Objects/natural/vegetation/grass/grass_groups/'
TREE = 'Objects/natural/vegetation/trees/normal_trees/quercus_robur/'
PARSER_SHA = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()


def cached_mesh(raw, output, *, visible_materials=None):
    """仅缓存无对象的数值数组；材质、着色器和当前树冠遮蔽仍按本次配置创建。"""
    source = hashlib.sha256(raw).hexdigest()
    selected = None if visible_materials is None else sorted(visible_materials)
    key = hashlib.sha256(json.dumps([PARSER_SHA, source, selected]).encode()).hexdigest()
    folder = output / 'parsed-meshes'
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / (key + '.npz')
    if path.exists():
        try:
            with np.load(path, allow_pickle=False) as stored:
                result = {name: stored[name].tolist() for name in ('points', 'normals', 'uv', 'faces', 'material_ids')}
            result['sha256'] = source
            return result
        except (OSError, ValueError, KeyError) as error:
            print('本地网格缓存失效，重新解析：', path, error)
    result = read_mesh(raw, visible_materials=visible_materials)
    temporary = path.with_suffix('.' + str(os.getpid()) + '.tmp.npz')
    np.savez(temporary, **{name: np.asarray(result[name]) for name in ('points', 'normals', 'uv', 'faces', 'material_ids')})
    temporary.replace(path)
    return result


def texture_cache_key(package, stem, options):
    """原包身份与相关成员CRC一起失效，避免读取上次安装或旧解码算法的数据。"""
    archive = Path(package.filename)
    stat = archive.stat()
    entries = [(v.filename, v.CRC, v.file_size) for v in package.infolist() if v.filename.startswith(stem)]
    return [PARSER_SHA, str(archive.resolve()), stat.st_size, stat.st_mtime_ns, entries, options]


def read_texture_cache(output, key, channels):
    manifest = output.with_suffix('.cache.json')
    if not manifest.exists():
        return None
    try:
        record = json.loads(manifest.read_text(encoding='utf-8'))
        if record != json.loads(json.dumps(key)):
            return None
        result = {}
        for channel in channels:
            path = output.with_name(output.stem + '-' + channel + '.txo')
            texture = Texture(output.stem + '-' + channel)
            if not texture.read(Filename.fromOsSpecific(str(path))):
                raise OSError(path)
            result[channel] = texture
        return result
    except (OSError, ValueError) as error:
        print('本地纹理缓存失效，重新解码：', output, error)
        return None


def write_texture_cache(output, key, textures):
    for channel, texture in textures.items():
        path = output.with_name(output.stem + '-' + channel + '.txo')
        temporary = path.with_name(path.stem + '.' + str(os.getpid()) + '.tmp.txo')
        if not texture.write(Filename.fromOsSpecific(str(temporary))):
            raise OSError(temporary)
        temporary.replace(path)
    manifest = output.with_suffix('.cache.json')
    temporary = manifest.with_suffix('.' + str(os.getpid()) + '.tmp')
    temporary.write_text(json.dumps(key), encoding='utf-8')
    temporary.replace(manifest)


def read_mesh(raw, *, visible_materials=None):
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
        if (visible_materials is None and material == 2) or (visible_materials is not None and material not in visible_materials):
            continue
        selected = values[first:first + length]
        faces.extend(zip(selected[::3], selected[1::3], selected[2::3], strict=True))
    return {'points': points, 'normals': normals, 'uv': uv, 'faces': faces,
            'material_ids': material_ids, 'sha256': hashlib.sha256(raw).hexdigest()}


def decode_texture(package, name, suffix, size, output, *, alpha_cutoff=.25):
    key = texture_cache_key(package, name, [suffix, size, alpha_cutoff])
    cached = read_texture_cache(output, key, ['color'])
    if cached is not None and output.exists() and output.with_name(output.stem + '-mip-coverage.json').exists():
        return cached['color']
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
    coverage = load_source_mips(texture, package, name, suffix, size, header, alpha_cutoff)
    output.with_name(output.stem + '-mip-coverage.json').write_text(json.dumps(coverage, indent=2), encoding='utf-8')
    write_texture_cache(output, key, {'color': texture})
    return texture


def load_source_mips(texture, package, name, suffix, size, header, cutoff):
    """保留作者实际制作的RGB/alpha mip；仅末端小于4像素的补全层采用引擎默认生成。"""
    texture.generateRamMipmapImages()
    result = [{'level': 0, 'source': name + suffix, 'alpha_cutoff': cutoff}]
    width, height = size
    stream, level, offset = int(suffix[1:]), 0, 148
    resident = package.read(name)
    block_size = 8 if struct.unpack_from('<I', header, 128)[0] == 71 else 16
    while min(width, height) > 4:
        width, height, stream, level = width // 2, height // 2, stream - 1, level + 1
        length = max(1, (width + 3) // 4) * max(1, (height + 3) // 4) * block_size
        if stream >= 1:
            source = name + '.' + str(stream)
            payload = package.read(source)
        else:
            source = name + '@' + str(offset)
            payload = resident[offset:offset + length]
            offset += length
        if len(payload) != length:
            raise ValueError('原件mip尺寸与实际数据不符：' + source)
        mip_header = bytearray(header)
        struct.pack_into('<II', mip_header, 12, height, width)
        rgba = np.asarray(Image.open(io.BytesIO(mip_header + payload)).convert('RGBA'))
        # Panda的RAM像素是自下而上的BGRA；源DDS解码图则是自上而下RGBA。
        native = rgba[::-1][:, :, [2, 1, 0, 3]]
        texture.setRamMipmapImage(level, PTAUchar(native.tobytes()))
        result.append({'level': level, 'source': source, 'size': [width, height],
                       'sha256': hashlib.sha256(payload).hexdigest(),
                       'coverage': float(np.mean(rgba[:, :, 3] / 255 >= cutoff))})
    return result


def detail_maps(package, stem, suffix, size, output, sss_suffix, sss_size):
    """同一原件的BC5法线、BC4光滑度与透光图；只写本地缓存。"""
    from prepare_kcd_environment import texture_image

    cache = output / (Path(stem).name + '-detail')
    key = texture_cache_key(package, stem, [suffix, size, sss_suffix, sss_size])
    channels = ['normal', 'gloss'] + (['transmission'] if sss_suffix is not None else [])
    cached = read_texture_cache(cache, key, channels)
    if cached is not None:
        return cached

    normal = np.asarray(texture_image(package, stem + '_ddna.dds', suffix, size), dtype=np.float32) / 255
    xy = normal[:, :, :2] * 2 - 1
    normal[:, :, 2] = np.sqrt(np.maximum(0, 1 - np.sum(xy * xy, axis=2))) * .5 + .5
    images = {
        'normal': Image.fromarray(np.uint8(np.clip(normal, 0, 1) * 255)),
        'gloss': texture_image(package, stem + '_ddna.dds', suffix, size, alpha=True).getchannel('R'),
    }
    if sss_suffix is not None:
        images['transmission'] = texture_image(package, stem + '_sss.dds', sss_suffix, sss_size)
    result = {}
    for channel, pixels in images.items():
        path = output / (Path(stem).name + '-' + channel + '.png')
        pixels.save(path)
        value = Texture(path.stem)
        if not value.read(Filename.fromOsSpecific(str(path))):
            raise OSError(path)
        value.setMinfilter(Texture.FTLinearMipmapLinear)
        value.setAnisotropicDegree(8)
        result[channel] = value
    write_texture_cache(cache, key, result)
    return result


def foliage_parameters(package, name, material_index=None):
    """读取原件的透光颜色/强度和视向法线依赖，不能将它们当成同一个高光系数。"""
    material = ET.fromstring(package.read(name))
    if material_index is not None:
        material = material.find('SubMaterials')[material_index]
    parameters = material.find('PublicParams').attrib
    return {'transmittance_color': tuple(float(v) for v in parameters['TransmittanceColor'].split(',')),
            'back_diffuse': float(parameters['BackDiffuseMultiplier']),
            'normal_view_dependency': float(parameters['NormalViewDependency']),
            'specular_color': tuple(float(v) for v in material.attrib['Specular'].split(',')),
            'alpha_cutoff': float(material.attrib['AlphaTest'])}


def model(name, mesh, texture, shader):
    colors = mesh['colors'] if 'colors' in mesh else [(1, 1, 1, 1)] * len(mesh['points'])
    node = surface_mesh(name, mesh['points'], mesh['faces'], mesh['normals'], colors, mesh['uv'])
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
    if 'maps' in mesh:
        for channel, value in mesh['maps'].items():
            node.setShaderInput('local_' + channel, value)
    if 'foliage' in mesh:
        for channel, value in mesh['foliage'].items():
            if channel == 'alpha_cutoff':
                node.setAttrib(AlphaTestAttrib.make(AlphaTestAttrib.MGreaterEqual, value))
                node.setShaderInput('foliage_alpha_cutoff', value)
            else:
                node.setShaderInput('local_' + channel, value)
    return node


def load_local(output, shader, *, distance_lods=False, tree_letters='abc', canopy_visibility=None):
    output.mkdir(parents=True, exist_ok=True)
    trees, grasses, record, materials = [], [], [], {}
    with ZipFile(INSTALL / 'IPL_Objects-part5.pak') as package:
        texture = decode_texture(package, TREE + 'quercus_atlas_diff.dds', '.5', (2048, 1024), output / 'oak.png')
        atlas_hash = hashlib.sha256(package.read(TREE + 'quercus_atlas_diff.dds')
                                    + package.read(TREE + 'quercus_atlas_diff.dds.5')).hexdigest()
        maps = detail_maps(package, TREE + 'quercus_atlas', '.5', (2048, 1024), output, '.5', (2048, 1024))
        parameters = [foliage_parameters(package, TREE + 'quercus_robur.mtl', index) for index in (1, 3, 6)]
        materials['oak'] = {'source': TREE + 'quercus_robur.mtl', 'lod_parameters': parameters}
        for letter in tree_letters:
            root = NodePath(FadeLODNode('kcd-oak-' + letter)) if distance_lods else None
            if root is not None:
                root.node().setFadeTime(.45)
                root.node().setFadeStateOverride(10)
            anchor_offset = None
            for level in range(3 if distance_lods else 1):
                suffix = '' if level == 0 else '_lod' + str(level)
                name = TREE + 'quercus_' + letter + suffix + '.cgfm'
                mesh = cached_mesh(package.read(name), output)
                if canopy_visibility is not None:
                    visibility = json.loads((canopy_visibility / ('quercus_' + letter + suffix + '.json')).read_text(encoding='utf-8'))
                    if visibility['source_sha256'] != mesh['sha256'] or len(visibility['sky_visibility']) != len(mesh['points']):
                        raise ValueError('树冠天空遮蔽与原网格不匹配：' + name)
                    if visibility['source_atlas_sha256'] != atlas_hash:
                        raise ValueError('树冠天空遮蔽与原atlas不匹配：' + name)
                    mesh['colors'] = [(value, value, value, 1.) for value in visibility['sky_visibility']]
                mesh['maps'] = maps
                mesh['foliage'] = parameters[level]
                if not set(mesh['material_ids']) <= {1, 2, 3, 6, 10, 12}:
                    raise ValueError((name, mesh['material_ids']))
                visible_base = min(mesh['points'][i][2] for face in mesh['faces'] for i in face)
                if level == 0:
                    # 原件以z=0种植，负高度是应埋入土中的根；不能按包围盒抬出锥形树根。
                    anchor_offset = -.03
                    visible_points = [mesh['points'][i] for face in mesh['faces'] for i in face]
                    height = max(p[2] for p in visible_points)
                    crown_radius = max(max(p[axis] for p in visible_points) - min(p[axis] for p in visible_points)
                                       for axis in (0, 1)) / 2
                part = model('kcd-oak-' + letter + suffix, mesh, texture, shader)
                part.setZ(anchor_offset)
                part.setShaderInput('root_anchor', anchor_offset)
                if distance_lods:
                    part.reparentTo(root)
                    root.node().addSwitch(*((45, 0), (130, 45), (700, 130))[level])
                else:
                    anchored = NodePath('anchored-kcd-oak-' + letter)
                    anchored.setTag('source-height', str(height))
                    anchored.setTag('source-crown-radius', str(crown_radius))
                    part.reparentTo(anchored)
                    trees.append(anchored)
                record.append({'source': name, 'triangles': len(mesh['faces']), 'sha256': mesh['sha256'],
                               'visible_base_z': visible_base, 'root_anchor': anchor_offset})
            if distance_lods:
                root.node().setCenter((0, 0, height * .5))
                root.setTag('source-height', str(height))
                root.setTag('source-crown-radius', str(crown_radius))
                trees.append(root)
    with ZipFile(INSTALL / 'IPL_Objects-part4.pak') as package:
        parameters = foliage_parameters(package, GRASS + 'grass.mtl', 0)
        texture = decode_texture(package, GRASS + 'plants_grass_merged_diff.dds', '.6', (2048, 2048), output / 'grass.png',
                                 alpha_cutoff=parameters['alpha_cutoff'])
        maps = detail_maps(package, GRASS + 'plants_grass_merged', '.6', 2048, output, '.6', 2048)
        materials['grass'] = {'source': GRASS + 'grass.mtl', 'parameters': parameters}
        for grass_name in ('grass_green_a', 'grass_green_b', 'grass_green_c',
                           'dry_grass_a', 'dry_grass_b', 'dry_grass_c', 'mixed_grass_a', 'mixed_grass_b'):
            name = GRASS + grass_name + '.cgfm'
            mesh = cached_mesh(package.read(name), output)
            mesh['maps'] = maps
            mesh['foliage'] = parameters
            grasses.append((mesh, texture))
            record.append({'source': name, 'triangles': len(mesh['faces']), 'sha256': mesh['sha256']})
    (output / 'local-source.json').write_text(json.dumps({
        'scope': '用户指定的本机KCD2资源试验；原件只读；衍生资源仅存ignored logs，不作为可分发资产',
        'installation': str(INSTALL), 'meshes': record, 'materials': materials,
    }, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    with ZipFile(INSTALL / 'IPL_Textures-part1.pak') as package:
        ground = decode_texture(package, 'Textures/terrain/grass/grass_pasture_a_2x2_diff.dds',
                                '.5', (1024, 1024), output / 'pasture.png')
    return trees, grasses, ground


def load_ferns(output, shader, grasses):
    """原蕨的CGF明确引用grass.mtl，复用其真实图集，不误用同目录的旧undergrowth贴图。"""
    base = 'Objects/natural/vegetation/forest_undergrowth/'
    material_name = GRASS + 'grass'
    source, texture = grasses[0]
    result, record = [], []
    with ZipFile(INSTALL / 'IPL_Objects-part4.pak') as package:
        for variant in ('a', 'b', 'large_a'):
            name = base + 'ferns_' + variant
            if material_name.encode() not in package.read(name + '.cgf'):
                raise ValueError('原蕨的材质引用已改变：' + name)
            root = NodePath(FadeLODNode('kcd-fern-' + variant))
            root.node().setFadeTime(.45)
            root.node().setFadeStateOverride(10)
            switches = ((65, 0), (130, 65), (185, 130)) if variant == 'large_a' else ((65, 0), (185, 65))
            for level, switch in enumerate(switches):
                member = name + ('' if level == 0 else '_lod'+str(level)) + '.cgfm'
                mesh = cached_mesh(package.read(member), output, visible_materials={0})
                if set(mesh['material_ids']) != {0}:
                    raise ValueError('原蕨含未确认的材质：' + member)
                mesh.update(maps=source['maps'], foliage=source['foliage'])
                part = model('kcd-fern-' + variant + '-lod' + str(level), mesh, texture, shader)
                part.setShaderInput('root_anchor', 0.)
                part.reparentTo(root)
                root.node().addSwitch(*switch)
                if level == 0:
                    root.setTag('source-height', str(max(p[2] for p in mesh['points'])))
                record.append({'source': member, 'source_sha256': mesh['sha256'],
                               'triangles': len(mesh['faces']), 'material_reference': material_name,
                               'visible_materials': [0]})
            result.append(root)
    (output / 'local-fern-source.json').write_text(json.dumps(record, indent=2), encoding='utf-8')
    return result


def load_shrubs(output, shader):
    """原始山楂灌丛补足林缘层；显式按其材质定义排除shadow_proxy=4。"""
    base = 'Objects/natural/vegetation/bushes/crataegus/'
    record, result = [], []
    with ZipFile(INSTALL / 'IPL_Objects-part4.pak') as package:
        parameters = foliage_parameters(package, base + 'crataegus.mtl', 1)
        texture = decode_texture(package, base + 'crataegus_branch_diff.dds', '.5', (1024, 1024),
                                 output / 'hawthorn.png', alpha_cutoff=parameters['alpha_cutoff'])
        maps = detail_maps(package, base + 'crataegus_branch', '.5', 1024, output, '.5', 1024)
        for variant in ('a', 'b', 'small_a'):
            name = base + 'crataegus_' + variant + '.cgfm'
            mesh = cached_mesh(package.read(name), output, visible_materials={1})
            mesh['maps'] = maps
            mesh['foliage'] = parameters
            part = model('kcd-hawthorn-' + variant, mesh, texture, shader)
            part.setShaderInput('root_anchor', 0.)
            lod = NodePath(FadeLODNode('kcd-hawthorn-' + variant + '-distance'))
            lod.node().setFadeTime(.45)
            lod.node().setFadeStateOverride(10)
            lod.node().addSwitch(220, 0)
            part.reparentTo(lod)
            lod.setTag('source-height', str(max(mesh['points'][i][2] for face in mesh['faces'] for i in face)))
            result.append(lod)
            record.append({'source': name, 'triangles': len(mesh['faces']), 'sha256': mesh['sha256'],
                           'source_materials': mesh['material_ids'], 'visible_materials': [1],
                           'material_parameters': parameters})
    (output / 'local-shrub-source.json').write_text(json.dumps(record, indent=2), encoding='utf-8')
    return result


def load_young_oaks(output, shader, atlas):
    """复用大橡树的同一图集与通道，载入真正低分枝的林下橡树。"""
    record, result = [], []
    texture = atlas.findAllTextures()[0]
    maps = {channel: atlas.getShaderInput('local_' + channel).getTexture()
            for channel in ('normal', 'gloss', 'transmission')}
    with ZipFile(INSTALL / 'IPL_Objects-part5.pak') as package:
        parameters = foliage_parameters(package, TREE + 'quercus_robur.mtl', 1)
        for variant in 'adf':
            name = TREE + 'quercus_undergrowth_' + variant + '.cgfm'
            mesh = cached_mesh(package.read(name), output, visible_materials={1})
            mesh.update(maps=maps, foliage=parameters)
            part = model('kcd-young-oak-' + variant, mesh, texture, shader)
            part.setShaderInput('root_anchor', 0.)
            root = NodePath(FadeLODNode('kcd-young-oak-' + variant + '-distance'))
            root.node().setFadeTime(.45)
            root.node().setFadeStateOverride(10)
            root.node().addSwitch(240, 0)
            part.reparentTo(root)
            height = max(mesh['points'][i][2] for face in mesh['faces'] for i in face)
            root.setTag('source-height', str(height))
            result.append(root)
            record.append({'source': name, 'triangles': len(mesh['faces']), 'sha256': mesh['sha256'],
                           'source_height': height, 'visible_materials': [1], 'material_parameters': parameters})
    (output / 'local-young-oak-source.json').write_text(json.dumps(record, indent=2), encoding='utf-8')
    return result


def load_sandstone(output, shader):
    """只读原件可见砂岩网格与三档LOD；按设计尺寸归一，原物理代理不加载。"""
    base = 'Objects/natural/rocks/sandstone_rocks/'
    result, record = {}, []
    with ZipFile(INSTALL / 'IPL_Objects-part4.pak') as package:
        stem = base + 'sandstone_rocks_b'
        texture = decode_texture(package, stem + '_diff.dds', '.5', (1024, 1024), output / 'sandstone.png')
        maps = detail_maps(package, stem, '.5', 1024, output, None, None)
        material = ET.fromstring(package.read(base + 'sandstone_rocks_b.mtl')).find('SubMaterials')[1]
        assert material.attrib['Shader'] == 'Illum'
        specular = tuple(float(v) for v in material.attrib['Specular'].split(','))
        for label in ('huge', 'large_a', 'large_b', 'medium', 'small'):
            root = NodePath(LODNode('kcd-sandstone-' + label))
            for level, switch in enumerate(((70, 0), (180, 70), (420, 180))):
                name = base + 'sandstone_rock_' + label + ('' if not level else '_lod' + str(level)) + '.cgfm'
                mesh = cached_mesh(package.read(name), output, visible_materials={1})
                mesh['maps'] = maps
                part = model('kcd-sandstone-' + label + '-lod' + str(level), mesh, texture, shader)
                part.setShaderInput('local_rock_specular', specular)
                part.reparentTo(root)
                root.node().addSwitch(*switch)
                if level == 0:
                    z = [mesh['points'][i][2] for face in mesh['faces'] for i in face]
                    root.setTag('source-height', str(max(z) - min(z)))
                    root.setTag('source-base', str(min(z)))
                record.append({'source': name, 'triangles': len(mesh['faces']), 'sha256': mesh['sha256'],
                               'visible_materials': [1], 'specular': specular})
            result[label] = root
    (output / 'local-sandstone-source.json').write_text(json.dumps(record, indent=2), encoding='utf-8')
    return result
