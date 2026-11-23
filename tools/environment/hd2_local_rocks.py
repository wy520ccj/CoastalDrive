"""读取本机HD2导出的原岩壁；本地材质样板不进入发行资源。"""

import io
import json
import struct
import sys
from pathlib import Path

import numpy as np
from panda3d.core import LODNode, Material, NodePath, PTAUchar, Shader, Texture, TextureStage
from PIL import Image

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'src'))

from environment.expressway_materials import add_distance_haze, add_shadow_transition
from environment.surface_mesh import surface_mesh

SOURCE = ROOT / 'logs/visual-upgrade-20261026/hd2-rock-turing/content/env_shared/assets/rocks/neutral/rock_cliff_face_01.unit.glb'


def read_source(path):
    """只读已确认的GLB2，保留原始数组；未知布局直接报错。"""
    raw = path.read_bytes()
    magic, version, total, length, kind = struct.unpack_from('<5I', raw)
    if (magic, version, total, kind) != (0x46546c67, 2, len(raw), 0x4e4f534a):
        raise ValueError('需要完整GLB2 JSON/BIN原件')
    document = json.loads(raw[20:20 + length])
    size, kind = struct.unpack_from('<II', raw, 20 + length)
    if kind != 0x004e4942 or 28 + length + size != len(raw):
        raise ValueError('GLB二进制块边界不符')
    return document, raw[28 + length:]


def accessor(document, binary, index):
    item = document['accessors'][index]
    if 'sparse' in item or item.get('normalized', False):
        raise ValueError('本次岩壁不使用稀疏或归一化访问器')
    view = document['bufferViews'][item['bufferView']]
    dtype = {5126: '<f4', 5123: '<u2', 5125: '<u4'}[item['componentType']]
    columns = {'SCALAR': 1, 'VEC2': 2, 'VEC3': 3, 'VEC4': 4}[item['type']]
    width = np.dtype(dtype).itemsize * columns
    stride = view.get('byteStride', width)
    offset = view.get('byteOffset', 0) + item.get('byteOffset', 0)
    end = item.get('byteOffset', 0) + max(0, item['count'] - 1) * stride + width
    if stride < width or end > view['byteLength'] or view.get('buffer', 0) != 0:
        raise ValueError('原件访问器越界')
    return np.ndarray((item['count'], columns), dtype=dtype, buffer=binary,
                      offset=offset, strides=(stride, np.dtype(dtype).itemsize)).copy()


def image_bytes(document, binary, index):
    view = document['bufferViews'][document['images'][index]['bufferView']]
    start = view.get('byteOffset', 0)
    return binary[start:start + view['byteLength']]


def resize_channels(image, size, resampling):
    """这些alpha是高度/泥土/粗糙度，不是透明度；缩放不得预乘后清零RGB。"""
    return Image.merge('RGBA', [channel.resize(size, resampling) for channel in image.split()])


def source_texture(document, binary, index, name, *, color=False):
    """PNG中的竖排层还原为真正数组纹理，逐层翻转而不是翻转整个数组。"""
    item = document['textures'][index]
    pixels = Image.open(io.BytesIO(image_bytes(document, binary, item['source']))).convert('RGBA')
    layers = item.get('extras', {}).get('layers', [1])[0]
    if pixels.height % layers:
        raise ValueError('原件数组层高不整除')
    height = pixels.height // layers
    # 样板固定1024上限，原解出图像和GLB仍完整保存；不冒称原引擎mip。
    width, target_height = min(1024, pixels.width), round(height * min(1, 1024 / pixels.width))
    slices = []
    for level in range(layers):
        layer = pixels.crop((0, level * height, pixels.width, (level + 1) * height))
        layer = resize_channels(layer, (width, target_height), Image.Resampling.LANCZOS)
        slices.append(layer)
    texture = Texture(name)
    texture_format = Texture.FSrgbAlpha if color else Texture.FRgba8
    if layers == 1:
        texture.setup2dTexture(width, target_height, Texture.TUnsignedByte, texture_format)
    else:
        texture.setup2dTextureArray(width, target_height, layers, Texture.TUnsignedByte, texture_format)
    # Panda1.10的数组RAM自动mip在多层触发内部断言；逐层构建，不把层数随mip缩小。
    level = 0
    while True:
        values = [np.asarray(layer)[::-1][:, :, [2, 1, 0, 3]].copy().tobytes() for layer in slices]
        if level == 0:
            texture.setRamImage(b''.join(values))
        else:
            texture.setRamMipmapImage(level, PTAUchar(b''.join(values)), width * target_height * 4)
        if width == target_height == 1:
            break
        width, target_height = max(1, width // 2), max(1, target_height // 2)
        slices = [resize_channels(layer, (width, target_height), Image.Resampling.BOX) for layer in slices]
        level += 1
    texture.setMinfilter(Texture.FTLinearMipmapLinear)
    texture.setAnisotropicDegree(8)
    return texture


DETAIL = '''
uniform sampler2DArray hd2_albedo;
uniform sampler2DArray hd2_data;
uniform sampler2D hd2_base;
uniform sampler2D hd2_mask;
uniform mat4 hd2_grading;
in vec3 hd2_object_position;
in vec3 hd2_object_normal;
vec2 hd2_projection() {
    vec3 n=abs(hd2_object_normal);
    return n.x>=n.y && n.x>=n.z ? hd2_object_position.yz :
           (n.y>=n.z ? hd2_object_position.xz : hd2_object_position.xy);
}
vec4 hd2_layers(sampler2DArray tex, vec2 uv, vec2 weight) {
    return mix(mix(texture(tex,vec3(uv,0.)),texture(tex,vec3(uv,1.)),weight.x),
               texture(tex,vec3(uv,2.)),weight.y);
}
vec2 hd2_weights(vec2 uv) {
    vec2 mask=texture(hd2_mask,v_texcoord).rg;
    float a=texture(hd2_albedo,vec3(uv,0.)).a;
    float b=texture(hd2_albedo,vec3(uv,1.)).a;
    float c=texture(hd2_albedo,vec3(uv,2.)).a;
    vec2 shaped=2.*mask*mask*(3.-2.*mask);
    return clamp(vec2((shaped.x+b-1.)-(a+1.-shaped.x),
                     (shaped.y+c-1.)-(mix(a,b,mask.x)+1.-shaped.y))*1.5+.5,0.,1.);
}
vec4 hd2_color() {
    vec2 uv=hd2_projection()*.25;
    vec3 color=hd2_layers(hd2_albedo,uv,hd2_weights(uv)).rgb;
    // 当前simplepbr日照标定；原星球色彩矩阵之后单独缩放，不声称原引擎照度。
    return vec4(clamp((hd2_grading*vec4(color,1.)).rgb,0.,1.)*.65,1.);
}
vec4 hd2_surface() {
    vec2 uv=hd2_projection()*.25;
    return hd2_layers(hd2_data,uv,hd2_weights(uv));
}
vec3 hd2_slope(vec2 slope,vec2 uv,vec3 n,vec3 dx,vec3 dy) {
    vec2 ux=dFdx(uv),uy=dFdy(uv);
    vec3 t=cross(dy,n)*ux.x+cross(n,dx)*uy.x;
    vec3 b=cross(dy,n)*ux.y+cross(n,dx)*uy.y;
    float magnitude=max(dot(t,t),dot(b,b));
    if(magnitude<1e-16) return vec3(0.);
    float z=sqrt(max(1.-dot(slope,slope),.000061*max(slope.x*slope.x,slope.y*slope.y)));
    return (t*slope.x-b*slope.y)/(z*sqrt(magnitude));
}
vec3 hd2_normal(vec3 geometric,vec3 position) {
    vec3 n=normalize(geometric);
    vec3 dx=dFdx(position),dy=dFdy(position);
    vec2 base=texture(hd2_base,v_texcoord).rg*2.-1.;
    vec2 detail=hd2_surface().rg*2.-1.;
    return normalize(n+hd2_slope(base,v_texcoord,n,dx,dy)
                      +hd2_slope(detail,hd2_projection()*.25,n,dx,dy));
}
'''


def rock_shader():
    from simplepbr._shaderutils import _load_shader_str

    defines = {'MAX_LIGHTS': 1, 'ENABLE_SHADOWS': True, 'USE_330': True}
    vertex = _load_shader_str('simplepbr.vert', defines.copy())
    vertex = vertex.replace('void main() {', 'out vec3 hd2_object_position;\nout vec3 hd2_object_normal;\nvoid main() {\n'
        'hd2_object_position=p3d_Vertex.xyz;\nhd2_object_normal=p3d_Normal;')
    fragment = _load_shader_str('simplepbr.frag', defines.copy())
    fragment = fragment.replace('void main() {', DETAIL + '\nvoid main() {')
    start = fragment.index('vec4 base_color = ')
    end = fragment.index(';', start)
    fragment = fragment[:start] + 'vec4 base_color = hd2_color() * p3d_ColorScale' + fragment[end:]
    fragment = fragment.replace('p3d_Material.roughness * metal_rough.g', 'clamp(hd2_surface().a,.08,1.)')
    fragment = fragment.replace('float ambient_occlusion = 1.0;',
        'float ambient_occlusion=texture(hd2_base,v_texcoord).b*mix(1.,hd2_surface().b,.5);')
    fragment = fragment.replace('normalize(v_view_tbn * normalmap)', 'hd2_normal(v_view_tbn[2],v_view_position)')
    fragment = fragment.replace('normalize(v_world_tbn * normalmap)', 'hd2_normal(v_world_tbn[2],v_world_position)')
    if 'hd2_color() * p3d_ColorScale' not in fragment:
        raise ValueError('当前simplepbr底色入口已变化')
    return Shader.make(Shader.SLGLSL, vertex, add_distance_haze(add_shadow_transition(fragment)))


def load_rock(path=SOURCE):
    from panda3d.core import Mat4

    document, binary = read_source(path)
    material = document['materials'][1]['extras']
    root = NodePath(LODNode('kcd-sandstone-hd2-cliff-face'))
    shader = rock_shader()
    for level in range(5):
        name = 'g_rock_cliff_face_01' + ('' if level == 0 else '_LOD' + str(level))
        entry, = [item for item in document['nodes'] if item['name'] == name and 'mesh' in item]
        primitive, = document['meshes'][entry['mesh']]['primitives']
        attributes = primitive['attributes']
        # glTF的Y朝上转换为Panda的Z朝上；法线同一正交变换，不重新计算。
        points = accessor(document, binary, attributes['POSITION'])[:, [0, 2, 1]] * [1, -1, 1]
        normals = accessor(document, binary, attributes['NORMAL'])[:, [0, 2, 1]] * [1, -1, 1]
        uv = accessor(document, binary, attributes['TEXCOORD_0']) * [1, -1] + [0, 1]
        faces = accessor(document, binary, primitive['indices']).reshape(-1, 3)
        if faces.max() >= len(points) or not np.all(np.isfinite(points)):
            raise ValueError('原件索引或坐标错误')
        part = surface_mesh('hd2-cliff-visible-lod' + str(level), points.tolist(), faces.tolist(),
                            normals.tolist(), [(1, 1, 1, 1)] * len(points), uv.tolist())
        part.reparentTo(root)
        root.node().addSwitch(*((70, 0), (150, 70), (260, 150), (420, 260), (700, 420))[level])
    for channel, key in (('albedo', 'triplanar_detail_albedo'), ('data', 'triplanar_detail_data'),
                         ('base', 'base_normal_ao_dirt'), ('mask', 'detail_mask_')):
        root.setShaderInput('hd2_' + channel, source_texture(document, binary, material[key], key,
                                                           color=channel == 'albedo'))
    # 原float16 DDS保留色彩矩阵中的负数和超1值，不能使用PNG预览恢复它。
    lut = document['textures'][material['asset_color_grading_lut']]['extensions']['MSFT_texture_dds']['source']
    raw = image_bytes(document, binary, lut)
    if struct.unpack_from('<I', raw, 128)[0] != 10:
        raise ValueError('本次确认的色彩矩阵应为RGBA16F DDS')
    values = np.frombuffer(raw[148:], dtype='<f2').reshape(-1, 4).astype(np.float32)
    group = int(material['grading_group_id'][0])
    matrix = np.eye(4, dtype=np.float32)
    matrix[:, :3] = values[(group - 1) * 4:group * 4, :3]
    root.setShaderInput('hd2_grading', Mat4(*matrix.flatten().tolist()))
    root.setShader(shader, 3)
    state = Material('hd2-local-stone')
    state.setBaseColor((1, 1, 1, 1))
    state.setRoughness(.9)
    state.setMetallic(0)
    root.setMaterial(state)
    # simplepbr默认底色采样器仍需完整纹理绑定。
    white = Texture('hd2-white')
    white.setup2dTexture(1, 1, Texture.TUnsignedByte, Texture.FRgba8)
    white.setRamImage(bytes([255] * 4))
    root.setTexture(TextureStage('Base Color'), white)
    low, high = root.getChild(0).getTightBounds()
    root.node().setCenter((low + high) * .5)
    root.setTag('source-height', str(high.z - low.z))
    root.setTag('source-base', str(low.z))
    return root
