"""显式本地投影实验：只替换已隔离的原树阴影几何，不接入默认入口。"""

import json
from zipfile import ZipFile

from kcd_local_assets import INSTALL, TREE, cached_mesh
from panda3d.core import BitMask32, GeomNode, Shader, ShaderAttrib

from environment.surface_mesh import surface_mesh


def load_proxies(cache):
    result, records = {}, []
    with ZipFile(INSTALL/'IPL_Objects-part5.pak') as package:
        for letter in 'abc':
            name = TREE+'quercus_'+letter+'_lod1.cgfm'
            mesh = cached_mesh(package.read(name), cache, visible_materials={2})
            if not mesh['faces']:
                raise ValueError('原树阴影代理为空：'+name)
            node = surface_mesh('local-shadow-proxy-'+letter, mesh['points'], mesh['faces'],
                                mesh['normals'], [(1, 1, 1, 1)]*len(mesh['points']), mesh['uv'])
            result[letter] = node.node().modifyGeom(0)
            records.append({'source': name, 'source_sha256': mesh['sha256'],
                            'material': 2, 'triangles': len(mesh['faces']), 'alpha_cutoff': .35})
    (cache/'shadow-proxy-sources.json').write_text(json.dumps(records, indent=2), encoding='utf-8')
    return result


def shadow_variant(scene):
    """沿用原影子着色器，仅将原常量改成有明确默认值的裁剪输入。"""
    light = scene.sun_path.node()
    original = light.getInitialState()
    attrib = original.getAttrib(ShaderAttrib)
    shader = attrib.getShader()
    fragment = shader.getText(Shader.STFragment)
    expected = 'if (base_color.a < .25) discard;'
    if fragment.count(expected) != 1:
        raise ValueError('阴影候选需要已确认的原alpha裁剪入口')
    fragment = fragment.replace('void main() {', 'uniform float local_shadow_cutoff;\nvoid main() {')
    fragment = fragment.replace(expected, 'if (base_color.a < local_shadow_cutoff) discard;')
    candidate = Shader.make(Shader.SLGLSL, shader.getText(Shader.STVertex), fragment)
    scene.render.setShaderInput('local_shadow_cutoff', .25)
    return original, original.setAttrib(attrib.setShader(candidate), 10), candidate


def shadow_originals(group, proxies):
    """只选主相机已隐藏、近远显示副本已独立的原树；不重写共享源模型。"""
    saved = []
    for tree in group.findAllMatches('**/+LODNode'):
        name = tree.getName()
        if not name.startswith('kcd-oak-') or not tree.isHidden(BitMask32.bit(0)):
            continue
        letter = name.removeprefix('kcd-oak-')
        part = tree.getChild(2)
        if not isinstance(part.node(), GeomNode) or part.node().getNumGeoms() != 1:
            raise ValueError('原树阴影几何结构已改变：'+name)
        geom = part.node().modifyGeom(0)
        saved.append((part, geom, proxies[letter]))
    if not saved:
        raise ValueError('没有找到已隔离的阴影原树')
    return saved


def set_variant(saved, enabled):
    for path, original, proxy in saved:
        path.node().setGeom(0, proxy if enabled else original)
        if enabled:
            path.setShaderInput('local_shadow_cutoff', .35)
        else:
            path.clearShaderInput('local_shadow_cutoff')
