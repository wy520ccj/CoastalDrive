"""设计26的连续岩坡；使用已登记的CC0扫描并跟随原道路分段回收。"""

import math
from pathlib import Path

from panda3d.core import Filename, Loader, LoaderOptions, LODNode, NodePath, Shader, Texture, Vec3

from environment.expressway_materials import add_distance_haze, add_shadow_transition
from environment.expressway_route import anchor

ROOT = Path(__file__).resolve().parents[2]

MOUNTAIN_MATERIAL = '''
uniform sampler2D expressway_rock;
vec4 expressway_albedo() {
    vec3 normal = normalize(v_world_tbn[2]);
    vec3 w = pow(abs(normal),vec3(4.));
    w /= max(w.x+w.y+w.z,.0001);
    vec3 p = v_world_position/18.;
    vec3 stone = texture(expressway_rock,p.yz).rgb*w.x
               + texture(expressway_rock,p.xz).rgb*w.y
               + texture(expressway_rock,p.xy).rgb*w.z;
    vec3 meadow = texture(p3d_TextureBaseColor,v_texcoord/4.).rgb;
    float macro = texture(p3d_TextureBaseColor,v_texcoord/80.+vec2(.37,.61)).g;
    // 沿用山体顶点RGB的林地色区；alpha只作岩量，不能把整座山当浅色草皮。
    vec3 forest = meadow*v_color.rgb*vec3(1.6,1.8,2.0)*(.75+macro*.5);
    float rocky = clamp(v_color.a+(stone.r-.12)*.8,0.,1.);
    vec3 rock = stone*vec3(.49,.48,.43);
    return vec4(mix(forest,rock,rocky),1.);
}
'''


def landscape_materials(kit):
    from kcd_local_environment import source_texture

    # 山体使用连续平铺图；扫描网格的UV图集只由其自身模型读取。
    path = ROOT / 'assets/game/expressway/strata-albedo.png'
    kit['rock'] = source_texture(path, color=True)
    shader = kit['mountain-shader']
    fragment = shader.getText(Shader.STFragment)
    start = fragment.index('uniform sampler2D expressway_rock;')
    end = fragment.index('\n}\n', start) + 3
    fragment = fragment[:start] + MOUNTAIN_MATERIAL + fragment[end:]
    kit['mountain-shader'] = Shader.make(Shader.SLGLSL, shader.getText(Shader.STVertex), fragment)


def rock_shader():
    from simplepbr._shaderutils import _load_shader_str

    defines = {'MAX_LIGHTS': 1, 'ENABLE_SHADOWS': True, 'USE_330': True,
               'USE_NORMAL_MAP': True, 'USE_OCCLUSION_MAP': True}
    vertex = _load_shader_str('simplepbr.vert', defines.copy())
    fragment = _load_shader_str('simplepbr.frag', defines.copy())
    # 原扫描包含切线；使用其GL法线、ARM和实际纹理尺度。
    return Shader.make(Shader.SLGLSL, vertex, add_distance_haze(add_shadow_transition(fragment)))


def sandstone_shader():
    from simplepbr._shaderutils import _load_shader_str

    defines = {'MAX_LIGHTS': 1, 'ENABLE_SHADOWS': True, 'USE_330': True}
    vertex = _load_shader_str('simplepbr.vert', defines.copy())
    fragment = _load_shader_str('simplepbr.frag', defines.copy())
    detail = '''
uniform sampler2D local_normal;
uniform sampler2D local_gloss;
uniform vec3 local_rock_specular;
vec3 sandstone_normal(vec3 n,vec3 p) {
    n = normalize(n);
    vec3 dx=dFdx(p),dy=dFdy(p);
    vec2 ux=dFdx(v_texcoord),uy=dFdy(v_texcoord);
    vec3 t=cross(dy,n)*ux.x+cross(n,dx)*uy.x;
    vec3 b=cross(dy,n)*ux.y+cross(n,dx)*uy.y;
    float magnitude=max(dot(t,t),dot(b,b));
    if(magnitude<1e-16) return n;
    vec3 normal=texture(local_normal,v_texcoord).rgb*2.-1.;
    normal.z*=sqrt(magnitude);
    float visible=1.;
    return normalize(mix(n,normalize(mat3(t,b,n)*normal),visible));
}
'''
    fragment = fragment.replace('void main() {', detail + '\nvoid main() {')
    fragment = fragment.replace('p3d_Material.roughness * metal_rough.g',
                                'max(.65,1.-texture(local_gloss,v_texcoord).r)')
    fragment = fragment.replace('vec3 spec_color = mix(F0, base_color.rgb, metallic);',
                                'vec3 spec_color = local_rock_specular;')
    fragment = fragment.replace('normalize(v_view_tbn * normalmap)', 'sandstone_normal(v_view_tbn[2],v_view_position)')
    fragment = fragment.replace('normalize(v_world_tbn * normalmap)', 'sandstone_normal(v_world_tbn[2],v_world_position)')
    return Shader.make(Shader.SLGLSL, vertex, add_distance_haze(add_shadow_transition(fragment)))


def load_rocks(parent):
    # 与车辆一样离线保存完整转换结果；进入道路时不重复计算扫描网格的切线。
    assets = []
    for name in ('coastal-rocks', 'driving-rocks'):
        path = ROOT/'assets/game/expressway/runtime-rocks'/(name+'.bam')
        if not path.is_file():
            raise FileNotFoundError('需先运行tools/environment/prepare_rock_runtime.py：'+str(path))
        node = Loader.getGlobalPtr().loadSync(Filename.fromOsSpecific(str(path)), LoaderOptions(LoaderOptions.LFNoCache))
        if node is None:
            raise OSError('无法读取岩岸运行资源：'+str(path))
        assets.append(NodePath(node))
    source, banks = assets
    shader, result = rock_shader(), {}
    for label in ('bank-a', 'bank-b', 'bank-c', 'shore'):
        node = NodePath(LODNode('local-coastal-' + label))
        node.node().setCenter((0, 0, 4 if label != 'shore' else 0))
        for level, switch in enumerate(((110, 0), (320, 110), (1050, 320))):
            part = (source if label == 'shore' else banks).find('**/' + label + '-lod' + str(level))
            if part.isEmpty():
                raise ValueError('岩岸缺少距离档：' + label + str(level))
            part.copyTo(node)
            node.node().addSwitch(*switch)
        node.setShader(shader, 3)
        node.reparentTo(parent)
        result[label] = node
    for asset in (source, banks):
        for texture in asset.findAllTextures():
            texture.setMinfilter(Texture.FTLinearMipmapLinear)
            texture.setAnisotropicDegree(8)
    return result


def outside_road(node, root, origin, curve):
    """真实变换后的保守外廓检查，覆盖组合弯另一支道路；4m采样保留额外净空。"""
    low, high = node.getTightBounds(root)
    # 包括真实外廓边缘，不把最后采样点额外伸到包围盒以外数米而误删安全的小岩块。
    xs = [low.x, *range(math.ceil(low.x / 4) * 4, math.floor(high.x / 4) * 4 + 1, 4), high.x]
    ys = [low.y, *range(math.ceil(low.y / 4) * 4, math.floor(high.y / 4) * 4 + 1, 4), high.y]
    for x in xs:
        for y in ys:
            world = (x + origin.x, y + origin.y)
            _s, lateral = curve.project(world) if curve else (world[1], world[0])
            if abs(lateral) < 13:
                return False
    return True


def rock_steps(root, index, seed, curve, kit, detail_parent, floor_point):
    origin = Vec3(*anchor(curve, index))
    # 短岩坡组成有间隔的林缘，而非把92m刚体长岩岸塞进紧弯。
    for number, (lateral, local, height_scale) in enumerate(((-38, 54, .7), (-38, 151, .65))):
        distance = index * 200 + local
        p = floor_point(curve, lateral, distance, seed)
        if p is None:
            continue
        label = 'bank-' + 'abc'[(index + number) % 3]
        node = kit['local-rocks'][label].copyTo(detail_parent(distance))
        node.setPos(p - origin - Vec3(0, 0, 1.2))
        node.setScale(.85, 1., height_scale)
        node.setH((curve.sample(distance).heading if curve else 0) + 90)
        node.setP(0)
        if not outside_road(node, root, origin, curve):
            node.removeNode()
            yield 'local-rock-road-clearance'
            continue
        yield 'local-coastal-cliff'
    # 完整砂岩巨石承担设计28的前排轮廓，后方暗崖只是脊线；大小石互相压叠、埋根。
    stones = ((-29, 50, 'huge', 6.5), (-34, 55, 'large_b', 4.2),
              (-21, 45, 'large_a', 2.2), (-30, 58, 'huge', 3.1), (-22, 56, 'small', 1.),
              (-24, 172, 'medium', 6.5), (-35, 178, 'large_a', 4.2),
              (-18, 165, 'large_b', 2.1), (-25, 176, 'huge', 3.5), (-19, 168, 'medium', 1.3),
              (22, 151, 'large_a', 1.2), (27, 161, 'small', .6))
    for number, (lateral, local, label, height) in enumerate(stones):
        distance = index * 200 + local
        p = floor_point(curve, lateral, distance, seed)
        if p is None or p.z < -2:
            continue
        use_hd2 = label == 'medium' and height == 6.5 and 'local-hd2-rock' in kit
        template = kit['local-hd2-rock'] if use_hd2 else kit['local-kcd-rocks'][label]
        node = template.copyTo(detail_parent(distance))
        if use_hd2:
            height = 4.2
        scale = height / float(node.getTag('source-height'))
        node.setScale(scale)
        node.setH(curve.sample(distance).heading if use_hd2 and curve is not None else
                  (index * 71 + (137 if number == 5 else number * 137)) % 360)
        node.setPos(p - origin + Vec3(0, 0, -float(node.getTag('source-base')) * scale - height * .23))
        if not outside_road(node, root, origin, curve):
            node.removeNode()
            continue
        yield 'local-sandstone-foot'
    # 岩岸仅用于确有低海岸的区域，山脊赛道不强行加入海面或岩岛。
    for local in (48, 146):
        distance = index * 200 + local
        p = floor_point(curve, 69, distance, seed)
        if p is None or p.z > 0:
            continue
        node = kit['local-rocks']['shore'].copyTo(detail_parent(distance))
        node.setPos(p.x - origin.x, p.y - origin.y, -2.4 - origin.z)
        node.setH((curve.sample(distance).heading if curve else 0) + 90)
        yield 'local-coastal-shore'
